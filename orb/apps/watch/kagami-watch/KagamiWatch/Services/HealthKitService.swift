//
// HealthKitService.swift — Native HealthKit Integration
//
// Colony: Nexus (e4) — Integration
//
// Extracts health data directly from Apple HealthKit and syncs to Kagami.
// No third-party apps required.
//
// Features:
//   - Background delivery for real-time updates
//   - Heart rate, HRV, sleep, activity, blood oxygen
//   - Automatic sync to Kagami API
//   - Battery-optimized batching
//   - Sleep tracking for auto-goodnight detection
//   - Workout detection for lighting adjustments
//   - Complication updates on health changes
//
// Permissions required:
//   - HealthKit capability in Xcode
//   - NSHealthShareUsageDescription in Info.plist
//
// Created: December 30, 2025
// Updated: December 31, 2025 — Added sleep/workout tracking
// 鏡

import Foundation
import HealthKit
import Combine
import WidgetKit
import WatchKit

@MainActor
class HealthKitService: ObservableObject {

    // MARK: - Published State

    @Published var isAuthorized = false
    @Published var authorizationDenied = false // Track if user explicitly denied
    @Published var lastSyncTime: Date?
    @Published var heartRate: Double?
    @Published var restingHeartRate: Double?
    @Published var hrv: Double?
    @Published var steps: Int = 0
    @Published var activeCalories: Int = 0
    @Published var exerciseMinutes: Int = 0
    @Published var bloodOxygen: Double?
    @Published var sleepHours: Double?

    // Sleep & Workout State
    @Published var isSleeping = false
    @Published var isWorkingOut = false
    @Published var currentWorkoutType: HKWorkoutActivityType?
    @Published var sleepState: SleepState = .awake
    @Published var lastSleepAnalysis: Date?

    // Scene Suggestions
    @Published var suggestedScene: SuggestedScene?

    // MARK: - Sleep State Enum

    enum SleepState: String {
        case awake
        case inBed       // In bed but not asleep
        case asleepLight // Core/light sleep
        case asleepDeep  // Deep sleep
        case asleepREM   // REM sleep
        case waking      // Just woke up

        var shouldTriggerGoodnight: Bool {
            switch self {
            case .inBed, .asleepLight, .asleepDeep, .asleepREM:
                return true
            case .awake, .waking:
                return false
            }
        }
    }

    // MARK: - Scene Suggestions

    enum SuggestedScene: String {
        case goodnight      // Sleep detected
        case wakeUp         // Waking detected
        case workoutLights  // Workout started
        case focusMode      // Low HR during work hours
        case relaxMode      // Evening + low activity
        case brightLights   // High activity

        var icon: String {
            switch self {
            case .goodnight: return "🌙"
            case .wakeUp: return "☀️"
            case .workoutLights: return "🏃"
            case .focusMode: return "🎯"
            case .relaxMode: return "🛋️"
            case .brightLights: return "💡"
            }
        }

        var apiScene: String {
            switch self {
            case .goodnight: return "goodnight"
            case .wakeUp: return "wake_up"
            case .workoutLights: return "workout"
            case .focusMode: return "focus"
            case .relaxMode: return "relax"
            case .brightLights: return "bright"
            }
        }
    }

    // MARK: - Internal

    private let healthStore = HKHealthStore()
    private var observerQueries: [HKObserverQuery] = []
    private var anchorQueries: [HKAnchoredObjectQuery] = []
    private var workoutSession: HKWorkoutSession?
    private var kagamiService: KagamiAPIService?

    // Sync batching
    private var pendingUpdates: [String: Any] = [:]
    private var syncDebounceTimer: Timer?
    private let syncDebounceInterval: TimeInterval = 5.0  // Batch updates for 5s

    // Scene suggestion tracking
    private var lastSuggestedScene: SuggestedScene?
    private var sceneSuggestionCooldown: Date?
    private let sceneCooldownInterval: TimeInterval = 300  // 5 min between suggestions

    // MARK: - Health Data Types

    private let readTypes: Set<HKObjectType> = [
        // Heart
        HKObjectType.quantityType(forIdentifier: .heartRate)!,
        HKObjectType.quantityType(forIdentifier: .restingHeartRate)!,
        HKObjectType.quantityType(forIdentifier: .heartRateVariabilitySDNN)!,

        // Activity
        HKObjectType.quantityType(forIdentifier: .stepCount)!,
        HKObjectType.quantityType(forIdentifier: .activeEnergyBurned)!,
        HKObjectType.quantityType(forIdentifier: .appleExerciseTime)!,
        HKObjectType.quantityType(forIdentifier: .distanceWalkingRunning)!,
        HKObjectType.quantityType(forIdentifier: .flightsClimbed)!,

        // Respiratory
        HKObjectType.quantityType(forIdentifier: .oxygenSaturation)!,
        HKObjectType.quantityType(forIdentifier: .respiratoryRate)!,

        // Sleep
        HKObjectType.categoryType(forIdentifier: .sleepAnalysis)!,

        // Workouts
        HKObjectType.workoutType(),
    ]

    // Authorization monitoring
    private var authorizationCancellable: AnyCancellable?

    // MARK: - Init

    init(kagamiService: KagamiAPIService? = nil) {
        self.kagamiService = kagamiService

        // Start monitoring authorization status changes
        startAuthorizationMonitoring()
    }

    deinit {
        authorizationCancellable?.cancel()
    }

    // MARK: - Authorization Monitoring

    /// Start monitoring for HealthKit authorization changes
    /// Per audit: Detects when user revokes permission in Settings
    private func startAuthorizationMonitoring() {
        // Check authorization status periodically and on notification
        // Note: HKHealthStore doesn't have a direct notification for auth changes,
        // so we poll on app activation and monitor key type statuses

        // Check initial status
        Task {
            await checkAuthorizationStatus()
        }

        // Monitor for app becoming active (user may have changed settings)
        // Per audit: Use WKApplication notification (watchOS 10+) with fallback
        if #available(watchOS 10.0, *) {
            NotificationCenter.default.addObserver(
                forName: WKApplication.didBecomeActiveNotification,
                object: nil,
                queue: .main
            ) { [weak self] _ in
                Task { @MainActor in
                    await self?.checkAuthorizationStatus()
                }
            }
        } else {
            // Fallback for watchOS 9 and earlier
            NotificationCenter.default.addObserver(
                forName: NSNotification.Name("WKApplicationDidBecomeActiveNotification"),
                object: nil,
                queue: .main
            ) { [weak self] _ in
                Task { @MainActor in
                    await self?.checkAuthorizationStatus()
                }
            }
        }
    }

    /// Check current authorization status for key HealthKit types
    /// Called on app activation to detect revoked permissions
    func checkAuthorizationStatus() async {
        guard HKHealthStore.isHealthDataAvailable() else {
            isAuthorized = false
            authorizationDenied = true
            KagamiLogger.health.warning("HealthKit not available on this device")
            return
        }

        // Check authorization status for key types
        let keyTypes: [HKObjectType] = [
            HKObjectType.quantityType(forIdentifier: .heartRate)!,
            HKObjectType.quantityType(forIdentifier: .stepCount)!,
            HKObjectType.categoryType(forIdentifier: .sleepAnalysis)!
        ]

        var anyAuthorized = false
        var anyDenied = false

        for type in keyTypes {
            let status = healthStore.authorizationStatus(for: type)
            switch status {
            case .sharingAuthorized:
                anyAuthorized = true
            case .sharingDenied:
                anyDenied = true
            case .notDetermined:
                break
            @unknown default:
                break
            }
        }

        let previousAuthStatus = isAuthorized

        if anyAuthorized {
            isAuthorized = true
            authorizationDenied = false
        } else if anyDenied {
            isAuthorized = false
            authorizationDenied = true
        }

        // Log status change if it occurred
        if previousAuthStatus != isAuthorized {
            if isAuthorized {
                KagamiLogger.health.info("HealthKit authorization restored")
                // Re-setup background delivery
                await setupBackgroundDelivery()
            } else {
                KagamiLogger.health.warning("HealthKit authorization revoked - background delivery disabled")
                // Clean up observer queries since we can't read data anymore
                stopObserverQueries()
            }
        }
    }

    /// Stop all observer queries (called when authorization is revoked)
    private func stopObserverQueries() {
        for query in observerQueries {
            healthStore.stop(query)
        }
        observerQueries.removeAll()

        for query in anchorQueries {
            healthStore.stop(query)
        }
        anchorQueries.removeAll()

        KagamiLogger.health.info("Stopped \(observerQueries.count) observer queries due to auth revocation")
    }

    /// Request user to re-authorize HealthKit (opens Settings)
    func openHealthKitSettings() {
        // On watchOS, we can't directly open Settings, but we can prompt for re-auth
        Task {
            _ = await requestAuthorization()
        }
    }

    // MARK: - Authorization

    func requestAuthorization() async -> Bool {
        guard HKHealthStore.isHealthDataAvailable() else {
            KagamiLogger.health.warning("HealthKit not available on this device")
            return false
        }

        do {
            try await healthStore.requestAuthorization(toShare: [], read: readTypes)
            isAuthorized = true
            KagamiLogger.health.info("HealthKit authorization granted")

            // Setup background delivery after authorization
            await setupBackgroundDelivery()

            // Setup sleep and workout monitoring
            setupSleepMonitoring()
            setupWorkoutMonitoring()

            // Initial data fetch
            await fetchAllCurrentData()

            return true
        } catch {
            KagamiLogger.health.error("HealthKit authorization failed: \(error.localizedDescription)")
            return false
        }
    }

    // MARK: - Background Delivery

    private func setupBackgroundDelivery() async {
        // Enable background delivery for critical metrics
        let backgroundTypes: [HKQuantityTypeIdentifier] = [
            .heartRate,
            .oxygenSaturation,
            .stepCount,
            .activeEnergyBurned,
        ]

        for typeId in backgroundTypes {
            guard let type = HKObjectType.quantityType(forIdentifier: typeId) else { continue }

            do {
                try await healthStore.enableBackgroundDelivery(for: type, frequency: .immediate)
                setupObserverQuery(for: type)
                KagamiLogger.health.logDebug("Background delivery enabled for \(typeId.rawValue)")
            } catch {
                KagamiLogger.health.error("Failed to enable background delivery for \(typeId.rawValue): \(error.localizedDescription)")
            }
        }

        // Sleep analysis (category type)
        if let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) {
            do {
                try await healthStore.enableBackgroundDelivery(for: sleepType, frequency: .immediate)
                KagamiLogger.health.logDebug("Background delivery enabled for sleep (immediate)")
            } catch {
                KagamiLogger.health.error("Failed to enable background delivery for sleep: \(error.localizedDescription)")
            }
        }

        // Workouts
        do {
            try await healthStore.enableBackgroundDelivery(for: HKObjectType.workoutType(), frequency: .immediate)
            KagamiLogger.health.logDebug("Background delivery enabled for workouts")
        } catch {
            KagamiLogger.health.error("Failed to enable background delivery for workouts: \(error.localizedDescription)")
        }
    }

    private func setupObserverQuery(for type: HKQuantityType) {
        let query = HKObserverQuery(sampleType: type, predicate: nil) { [weak self] _, completionHandler, error in
            if let error = error {
                KagamiLogger.health.error("Observer query error: \(error.localizedDescription)")
                completionHandler()
                return
            }

            Task { @MainActor [weak self] in
                await self?.handleNewData(for: type)
            }

            completionHandler()
        }

        healthStore.execute(query)
        observerQueries.append(query)
    }

    // MARK: - Sleep Monitoring

    private func setupSleepMonitoring() {
        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else { return }

        // Use anchored query for real-time sleep updates
        let anchor = HKQueryAnchor.init(fromValue: 0)

        let query = HKAnchoredObjectQuery(
            type: sleepType,
            predicate: nil,
            anchor: anchor,
            limit: HKObjectQueryNoLimit
        ) { [weak self] _, samples, _, _, _ in
            Task { @MainActor [weak self] in
                self?.processSleepSamples(samples as? [HKCategorySample] ?? [])
            }
        }

        // Update handler for real-time changes
        query.updateHandler = { [weak self] _, samples, _, _, _ in
            Task { @MainActor [weak self] in
                self?.processSleepSamples(samples as? [HKCategorySample] ?? [])
            }
        }

        healthStore.execute(query)
        anchorQueries.append(query)
        KagamiLogger.health.info("Sleep monitoring started with anchored query")
    }

    private func processSleepSamples(_ samples: [HKCategorySample]) {
        guard !samples.isEmpty else { return }

        // Get most recent sleep sample
        let sortedSamples = samples.sorted { $0.endDate > $1.endDate }
        guard let mostRecent = sortedSamples.first else { return }

        // Determine sleep state from sample value
        let previousState = sleepState

        switch mostRecent.value {
        case HKCategoryValueSleepAnalysis.inBed.rawValue:
            sleepState = .inBed
            isSleeping = false  // In bed but not asleep yet

        case HKCategoryValueSleepAnalysis.asleepCore.rawValue:
            sleepState = .asleepLight
            isSleeping = true

        case HKCategoryValueSleepAnalysis.asleepDeep.rawValue:
            sleepState = .asleepDeep
            isSleeping = true

        case HKCategoryValueSleepAnalysis.asleepREM.rawValue:
            sleepState = .asleepREM
            isSleeping = true

        case HKCategoryValueSleepAnalysis.asleep.rawValue:
            sleepState = .asleepLight  // Generic asleep
            isSleeping = true

        case HKCategoryValueSleepAnalysis.awake.rawValue:
            // Check if transitioning from sleep
            if previousState.shouldTriggerGoodnight {
                sleepState = .waking
            } else {
                sleepState = .awake
            }
            isSleeping = false

        default:
            sleepState = .awake
            isSleeping = false
        }

        lastSleepAnalysis = Date()

        // Update shared container for complications
        updateSharedHealthState()

        // Suggest scene based on sleep transition
        if sleepState != previousState {
            handleSleepStateTransition(from: previousState, to: sleepState)
        }

        KagamiLogger.health.info("Sleep state: \(sleepState.rawValue), isSleeping: \(self.isSleeping)")
        scheduleSyncToKagami()
    }

    private func handleSleepStateTransition(from previousState: SleepState, to newState: SleepState) {
        // Transitioning to sleep = suggest goodnight
        if !previousState.shouldTriggerGoodnight && newState.shouldTriggerGoodnight {
            suggestScene(.goodnight)
        }

        // Waking up = suggest wake up lights
        if previousState.shouldTriggerGoodnight && newState == .waking {
            suggestScene(.wakeUp)
        }
    }

    // MARK: - Workout Monitoring

    private func setupWorkoutMonitoring() {
        // Monitor for active workouts using anchored query
        let query = HKAnchoredObjectQuery(
            type: HKObjectType.workoutType(),
            predicate: nil,
            anchor: nil,
            limit: HKObjectQueryNoLimit
        ) { [weak self] _, samples, _, _, _ in
            Task { @MainActor [weak self] in
                self?.processWorkoutSamples(samples as? [HKWorkout] ?? [])
            }
        }

        query.updateHandler = { [weak self] _, samples, _, _, _ in
            Task { @MainActor [weak self] in
                self?.processWorkoutSamples(samples as? [HKWorkout] ?? [])
            }
        }

        healthStore.execute(query)
        anchorQueries.append(query)

        // Also observe workout sessions
        observeWorkoutSessions()

        KagamiLogger.health.info("Workout monitoring started")
    }

    private func observeWorkoutSessions() {
        // Check for currently running workouts
        let predicate = HKQuery.predicateForWorkouts(with: .running)

        let query = HKSampleQuery(
            sampleType: HKObjectType.workoutType(),
            predicate: predicate,
            limit: 1,
            sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]
        ) { [weak self] _, samples, _ in
            Task { @MainActor [weak self] in
                if let workout = samples?.first as? HKWorkout {
                    self?.isWorkingOut = true
                    self?.currentWorkoutType = workout.workoutActivityType
                    self?.updateSharedHealthState()
                    self?.suggestScene(.workoutLights)
                }
            }
        }

        healthStore.execute(query)
    }

    private func processWorkoutSamples(_ workouts: [HKWorkout]) {
        guard !workouts.isEmpty else { return }

        // Check if there's an ongoing workout (recent with duration still accumulating)
        let now = Date()
        let recentWorkouts = workouts.filter { now.timeIntervalSince($0.startDate) < 3600 }

        if let activeWorkout = recentWorkouts.first {
            // Check if workout is still active (ended recently or still going)
            let workoutEndedRecently = now.timeIntervalSince(activeWorkout.endDate) < 60

            if activeWorkout.duration == 0 || workoutEndedRecently {
                // Likely still active
                if !isWorkingOut {
                    isWorkingOut = true
                    currentWorkoutType = activeWorkout.workoutActivityType
                    updateSharedHealthState()
                    suggestScene(.workoutLights)
                    KagamiLogger.health.info("Workout detected: \(activeWorkout.workoutActivityType.name)")
                }
            } else if isWorkingOut {
                // Workout ended
                isWorkingOut = false
                currentWorkoutType = nil
                updateSharedHealthState()
                KagamiLogger.health.info("Workout ended")
            }
        }

        scheduleSyncToKagami()
    }

    // MARK: - Heart Rate Based Suggestions

    private func evaluateHeartRateForSuggestions() {
        guard let hr = heartRate else { return }

        let hour = Calendar.current.component(.hour, from: Date())

        // High heart rate during activity = bright lights
        if hr > 120 && !isWorkingOut {
            suggestScene(.brightLights)
            return
        }

        // Low heart rate in evening = relax mode
        if hr < 65 && hour >= 19 && hour < 22 && !isSleeping {
            suggestScene(.relaxMode)
            return
        }

        // Low heart rate late evening = goodnight
        if hr < 60 && hour >= 22 && !isSleeping {
            suggestScene(.goodnight)
            return
        }

        // Low/steady heart rate during work hours = focus
        if hr < 70 && hour >= 9 && hour < 17 && !isWorkingOut {
            suggestScene(.focusMode)
            return
        }
    }

    // MARK: - Scene Suggestion

    private func suggestScene(_ scene: SuggestedScene) {
        // Check cooldown
        if let cooldown = sceneSuggestionCooldown,
           Date().timeIntervalSince(cooldown) < sceneCooldownInterval,
           scene == lastSuggestedScene {
            return
        }

        suggestedScene = scene
        lastSuggestedScene = scene
        sceneSuggestionCooldown = Date()

        // Update complications
        ComplicationUpdateManager.shared.reloadAllComplications()

        // Add to pending updates for Kagami
        pendingUpdates["suggested_scene"] = scene.apiScene

        print("💡 Scene suggestion: \(scene.rawValue)")
    }

    /// Clear current scene suggestion
    func clearSuggestion() {
        suggestedScene = nil
    }

    /// Execute the suggested scene
    func executeSuggestedScene() async {
        guard let scene = suggestedScene,
              let api = kagamiService else { return }

        switch scene {
        case .goodnight:
            await api.executeScene("goodnight")
        case .wakeUp:
            await api.setLights(80)
        case .workoutLights:
            await api.setLights(100)
        case .focusMode:
            await api.setLights(60, rooms: ["Office"])
        case .relaxMode:
            await api.setLights(40)
        case .brightLights:
            await api.setLights(100)
        }

        clearSuggestion()
    }

    // MARK: - Shared Container for Complications

    private func updateSharedHealthState() {
        let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
        defaults?.set(heartRate ?? 0, forKey: "lastHeartRate")
        defaults?.set(isWorkingOut, forKey: "isWorkingOut")
        defaults?.set(isSleeping, forKey: "isSleeping")
        defaults?.set(sleepState.rawValue, forKey: "sleepState")

        // Trigger complication update
        ComplicationUpdateManager.shared.healthDataChanged(
            heartRate: heartRate,
            isWorkingOut: isWorkingOut,
            isSleeping: isSleeping
        )
    }

    // MARK: - Data Fetching

    private func handleNewData(for type: HKQuantityType) async {
        switch type.identifier {
        case HKQuantityTypeIdentifier.heartRate.rawValue:
            await fetchHeartRate()
            evaluateHeartRateForSuggestions()
        case HKQuantityTypeIdentifier.restingHeartRate.rawValue:
            await fetchRestingHeartRate()
        case HKQuantityTypeIdentifier.heartRateVariabilitySDNN.rawValue:
            await fetchHRV()
        case HKQuantityTypeIdentifier.stepCount.rawValue:
            await fetchSteps()
        case HKQuantityTypeIdentifier.activeEnergyBurned.rawValue:
            await fetchActiveCalories()
        case HKQuantityTypeIdentifier.appleExerciseTime.rawValue:
            await fetchExerciseMinutes()
        case HKQuantityTypeIdentifier.oxygenSaturation.rawValue:
            await fetchBloodOxygen()
        default:
            break
        }

        updateSharedHealthState()
        scheduleSyncToKagami()
    }

    func fetchAllCurrentData() async {
        await withTaskGroup(of: Void.self) { group in
            group.addTask { await self.fetchHeartRate() }
            group.addTask { await self.fetchRestingHeartRate() }
            group.addTask { await self.fetchHRV() }
            group.addTask { await self.fetchSteps() }
            group.addTask { await self.fetchActiveCalories() }
            group.addTask { await self.fetchExerciseMinutes() }
            group.addTask { await self.fetchBloodOxygen() }
            group.addTask { await self.fetchSleepData() }
        }

        updateSharedHealthState()
        await syncToKagami()
    }

    // MARK: - Individual Metric Fetches

    private func fetchHeartRate() async {
        guard let type = HKQuantityType.quantityType(forIdentifier: .heartRate) else { return }

        let value = await fetchMostRecentQuantity(type: type, unit: HKUnit.count().unitDivided(by: .minute()))
        heartRate = value
        pendingUpdates["heart_rate"] = value
    }

    private func fetchRestingHeartRate() async {
        guard let type = HKQuantityType.quantityType(forIdentifier: .restingHeartRate) else { return }

        let value = await fetchMostRecentQuantity(type: type, unit: HKUnit.count().unitDivided(by: .minute()))
        restingHeartRate = value
        pendingUpdates["resting_heart_rate"] = value
    }

    private func fetchHRV() async {
        guard let type = HKQuantityType.quantityType(forIdentifier: .heartRateVariabilitySDNN) else { return }

        let value = await fetchMostRecentQuantity(type: type, unit: HKUnit.secondUnit(with: .milli))
        hrv = value
        pendingUpdates["hrv"] = value
    }

    private func fetchSteps() async {
        guard let type = HKQuantityType.quantityType(forIdentifier: .stepCount) else { return }

        let value = await fetchTodaySum(type: type, unit: HKUnit.count())
        steps = Int(value ?? 0)
        pendingUpdates["steps"] = steps
    }

    private func fetchActiveCalories() async {
        guard let type = HKQuantityType.quantityType(forIdentifier: .activeEnergyBurned) else { return }

        let value = await fetchTodaySum(type: type, unit: HKUnit.kilocalorie())
        activeCalories = Int(value ?? 0)
        pendingUpdates["active_calories"] = activeCalories
    }

    private func fetchExerciseMinutes() async {
        guard let type = HKQuantityType.quantityType(forIdentifier: .appleExerciseTime) else { return }

        let value = await fetchTodaySum(type: type, unit: HKUnit.minute())
        exerciseMinutes = Int(value ?? 0)
        pendingUpdates["exercise_minutes"] = exerciseMinutes
    }

    private func fetchBloodOxygen() async {
        guard let type = HKQuantityType.quantityType(forIdentifier: .oxygenSaturation) else { return }

        let value = await fetchMostRecentQuantity(type: type, unit: HKUnit.percent())
        bloodOxygen = value.map { $0 * 100 }  // Convert to percentage
        pendingUpdates["blood_oxygen"] = bloodOxygen
    }

    private func fetchSleepData() async {
        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else { return }

        // Get last night's sleep (midnight to now)
        let calendar = Calendar.current
        let now = Date()
        let startOfDay = calendar.startOfDay(for: now)
        let predicate = HKQuery.predicateForSamples(withStart: startOfDay.addingTimeInterval(-12 * 3600), end: now)

        let samples: [HKCategorySample] = await withCheckedContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: sleepType,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]
            ) { _, samples, _ in
                continuation.resume(returning: samples as? [HKCategorySample] ?? [])
            }
            healthStore.execute(query)
        }

        // Calculate total sleep (asleep samples only)
        var totalSleep: TimeInterval = 0
        for sample in samples {
            let value = sample.value
            // AsleepCore, AsleepDeep, AsleepREM (iOS 16+) or InBed/Asleep (older)
            if value == HKCategoryValueSleepAnalysis.asleepCore.rawValue ||
               value == HKCategoryValueSleepAnalysis.asleepDeep.rawValue ||
               value == HKCategoryValueSleepAnalysis.asleepREM.rawValue ||
               value == HKCategoryValueSleepAnalysis.asleep.rawValue {
                totalSleep += sample.endDate.timeIntervalSince(sample.startDate)
            }
        }

        sleepHours = totalSleep / 3600.0
        pendingUpdates["sleep_hours"] = sleepHours

        // Process recent samples for current state
        processSleepSamples(samples)
    }

    // MARK: - Query Helpers

    private func fetchMostRecentQuantity(type: HKQuantityType, unit: HKUnit) async -> Double? {
        return await withCheckedContinuation { continuation in
            let predicate = HKQuery.predicateForSamples(
                withStart: Date().addingTimeInterval(-24 * 3600),
                end: Date()
            )

            let query = HKSampleQuery(
                sampleType: type,
                predicate: predicate,
                limit: 1,
                sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]
            ) { _, samples, _ in
                guard let sample = samples?.first as? HKQuantitySample else {
                    continuation.resume(returning: nil)
                    return
                }
                continuation.resume(returning: sample.quantity.doubleValue(for: unit))
            }

            healthStore.execute(query)
        }
    }

    private func fetchTodaySum(type: HKQuantityType, unit: HKUnit) async -> Double? {
        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: Date())

        return await withCheckedContinuation { continuation in
            let predicate = HKQuery.predicateForSamples(withStart: startOfDay, end: Date())

            let query = HKStatisticsQuery(
                quantityType: type,
                quantitySamplePredicate: predicate,
                options: .cumulativeSum
            ) { _, result, _ in
                guard let sum = result?.sumQuantity() else {
                    continuation.resume(returning: nil)
                    return
                }
                continuation.resume(returning: sum.doubleValue(for: unit))
            }

            healthStore.execute(query)
        }
    }

    // MARK: - Sync to Kagami

    private func scheduleSyncToKagami() {
        syncDebounceTimer?.invalidate()
        syncDebounceTimer = Timer.scheduledTimer(withTimeInterval: syncDebounceInterval, repeats: false) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.syncToKagami()
            }
        }
    }

    func syncToKagami() async {
        guard !pendingUpdates.isEmpty else { return }

        // Add sleep/workout state
        pendingUpdates["is_sleeping"] = isSleeping
        pendingUpdates["is_working_out"] = isWorkingOut
        pendingUpdates["sleep_state"] = sleepState.rawValue

        let payload: [String: Any] = [
            "source": "healthkit",
            "device": "apple_watch",
            "timestamp": ISO8601DateFormatter().string(from: Date()),
            "metrics": pendingUpdates,
        ]

        // POST to Kagami health endpoint
        guard let url = URL(string: "http://kagami.local:8001/api/health/ingest") else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)

        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                pendingUpdates.removeAll()
                lastSyncTime = Date()
                print("✅ Health data synced to Kagami")
            }
        } catch {
            print("❌ Failed to sync health data: \(error)")
        }
    }

    // MARK: - Cleanup

    func stop() {
        for query in observerQueries {
            healthStore.stop(query)
        }
        observerQueries.removeAll()

        for query in anchorQueries {
            healthStore.stop(query)
        }
        anchorQueries.removeAll()

        syncDebounceTimer?.invalidate()
    }
}

// MARK: - Workout Activity Type Extension

extension HKWorkoutActivityType {
    var name: String {
        switch self {
        case .running: return "Running"
        case .cycling: return "Cycling"
        case .walking: return "Walking"
        case .hiking: return "Hiking"
        case .swimming: return "Swimming"
        case .yoga: return "Yoga"
        case .functionalStrengthTraining: return "Strength"
        case .highIntensityIntervalTraining: return "HIIT"
        case .elliptical: return "Elliptical"
        case .rowing: return "Rowing"
        case .stairClimbing: return "Stairs"
        case .crossTraining: return "Cross Training"
        default: return "Workout"
        }
    }

    /// Suggested light level for this workout type
    var suggestedLightLevel: Int {
        switch self {
        case .yoga, .pilates, .mindAndBody:
            return 50  // Calmer lighting
        case .running, .cycling, .highIntensityIntervalTraining:
            return 100  // Full brightness
        default:
            return 80  // Standard workout lighting
        }
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * Sleep is the reset.
 * Workout is the activation.
 * Heart rate is the signal.
 */
