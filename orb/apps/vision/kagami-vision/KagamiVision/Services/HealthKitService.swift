//
// HealthKitService.swift — Native HealthKit Integration for visionOS
//
// Colony: Nexus (e₄) — Integration
//
// Extracts health data directly from Apple HealthKit on Vision Pro.
// Syncs to Kagami API automatically.
//
// Features:
//   - Read heart rate, HRV, activity from paired iPhone
//   - Display health metrics in spatial UI
//   - Sync to Kagami for cross-device awareness
//
// Note: visionOS accesses HealthKit through paired iPhone
//
// Created: December 30, 2025
// 鏡

import Foundation
import HealthKit
import Combine
import os.log

@MainActor
class HealthKitService: ObservableObject {

    // MARK: - Published State

    @Published var isAuthorized = false
    @Published var isAvailable = false
    @Published var lastSyncTime: Date?

    // Current metrics
    @Published var heartRate: Double?
    @Published var restingHeartRate: Double?
    @Published var hrv: Double?
    @Published var steps: Int = 0
    @Published var activeCalories: Int = 0
    @Published var exerciseMinutes: Int = 0
    @Published var bloodOxygen: Double?
    @Published var sleepHours: Double?

    // MARK: - Internal

    private let healthStore = HKHealthStore()
    private var observerQueries: [HKObserverQuery] = []

    // Sync batching
    private var pendingUpdates: [String: Any] = [:]
    private var syncDebounceTimer: Timer?
    private let syncDebounceInterval: TimeInterval = 10.0

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

        // Respiratory
        HKObjectType.quantityType(forIdentifier: .oxygenSaturation)!,

        // Sleep
        HKObjectType.categoryType(forIdentifier: .sleepAnalysis)!,
    ]

    // MARK: - Init

    init() {
        isAvailable = HKHealthStore.isHealthDataAvailable()
    }

    // MARK: - Authorization

    func requestAuthorization() async -> Bool {
        guard isAvailable else {
            KagamiLogger.healthKit.warning("HealthKit not available on this device")
            return false
        }

        do {
            try await healthStore.requestAuthorization(toShare: [], read: readTypes)
            isAuthorized = true
            KagamiLogger.healthKit.info("HealthKit authorization granted")

            // Initial data fetch
            await fetchAllCurrentData()

            // Setup background queries
            setupObserverQueries()

            return true
        } catch {
            KagamiLogger.logError("HealthKit authorization failed", error: error, logger: KagamiLogger.healthKit)
            return false
        }
    }

    // MARK: - Observer Queries

    private func setupObserverQueries() {
        let types: [HKQuantityTypeIdentifier] = [
            .heartRate,
            .stepCount,
            .activeEnergyBurned,
        ]

        for typeId in types {
            guard let type = HKObjectType.quantityType(forIdentifier: typeId) else { continue }

            let query = HKObserverQuery(sampleType: type, predicate: nil) { [weak self] _, completionHandler, error in
                if let error = error {
                    KagamiLogger.logError("Observer error", error: error, logger: KagamiLogger.healthKit)
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
    }

    // MARK: - Data Handling

    private func handleNewData(for type: HKQuantityType) async {
        switch type.identifier {
        case HKQuantityTypeIdentifier.heartRate.rawValue:
            await fetchHeartRate()
        case HKQuantityTypeIdentifier.stepCount.rawValue:
            await fetchSteps()
        case HKQuantityTypeIdentifier.activeEnergyBurned.rawValue:
            await fetchActiveCalories()
        default:
            break
        }

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

        await syncToKagami()
    }

    // MARK: - Individual Fetches

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
        bloodOxygen = value.map { $0 * 100 }
        pendingUpdates["blood_oxygen"] = bloodOxygen
    }

    private func fetchSleepData() async {
        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else { return }

        let calendar = Calendar.current
        let now = Date()
        let startOfDay = calendar.startOfDay(for: now)
        let predicate = HKQuery.predicateForSamples(withStart: startOfDay.addingTimeInterval(-12 * 3600), end: now)

        let samples: [HKCategorySample] = await withCheckedContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: sleepType,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: nil
            ) { _, samples, _ in
                continuation.resume(returning: samples as? [HKCategorySample] ?? [])
            }
            healthStore.execute(query)
        }

        var totalSleep: TimeInterval = 0
        for sample in samples {
            let value = sample.value
            if value == HKCategoryValueSleepAnalysis.asleepCore.rawValue ||
               value == HKCategoryValueSleepAnalysis.asleepDeep.rawValue ||
               value == HKCategoryValueSleepAnalysis.asleepREM.rawValue ||
               value == HKCategoryValueSleepAnalysis.asleep.rawValue {
                totalSleep += sample.endDate.timeIntervalSince(sample.startDate)
            }
        }

        sleepHours = totalSleep / 3600.0
        pendingUpdates["sleep_hours"] = sleepHours
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

        let payload: [String: Any] = [
            "source": "healthkit",
            "device": "vision_pro",
            "timestamp": ISO8601DateFormatter().string(from: Date()),
            "metrics": pendingUpdates,
        ]

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
                KagamiLogger.healthKit.info("Health data synced to Kagami from Vision Pro")
            }
        } catch {
            KagamiLogger.logError("Failed to sync health data", error: error, logger: KagamiLogger.healthKit)
        }
    }

    // MARK: - Cleanup

    func stop() {
        for query in observerQueries {
            healthStore.stop(query)
        }
        observerQueries.removeAll()
        syncDebounceTimer?.invalidate()
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 */
