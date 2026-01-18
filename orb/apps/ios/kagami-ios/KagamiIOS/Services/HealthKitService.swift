//
// HealthKitService.swift — iOS HealthKit Integration
//
// Colony: Nexus (e₄) — Integration
//
// Features:
//   - Heart rate monitoring
//   - HRV (Heart Rate Variability)
//   - Step count tracking
//   - Sleep analysis
//   - Activity tracking (active calories, exercise minutes)
//   - Blood oxygen (SpO2)
//
// Architecture:
//   HealthKit → HealthKitService → KagamiAPIService → Kagami Backend
//

import Foundation
import HealthKit
import Combine

/// HealthKit integration service for iOS.
/// Reads biometric data and makes it available for upload to Kagami.
@MainActor
class HealthKitService: ObservableObject {

    static let shared = HealthKitService()

    // MARK: - Published State

    @Published var isAuthorized = false
    @Published var heartRate: Double = 0
    @Published var restingHeartRate: Double = 0
    @Published var hrv: Double = 0
    @Published var steps: Int = 0
    @Published var activeCalories: Double = 0
    @Published var exerciseMinutes: Double = 0
    @Published var bloodOxygen: Double = 0
    @Published var sleepHours: Double = 0

    // MARK: - Internal State

    private let healthStore = HKHealthStore()
    private var refreshTimer: Timer?
    private let refreshInterval: TimeInterval = 60.0  // Refresh every minute

    // MARK: - HealthKit Types

    private let readTypes: Set<HKSampleType> = {
        var types = Set<HKSampleType>()

        // Heart rate types
        if let heartRate = HKObjectType.quantityType(forIdentifier: .heartRate) {
            types.insert(heartRate)
        }
        if let restingHR = HKObjectType.quantityType(forIdentifier: .restingHeartRate) {
            types.insert(restingHR)
        }
        if let hrv = HKObjectType.quantityType(forIdentifier: .heartRateVariabilitySDNN) {
            types.insert(hrv)
        }

        // Activity types
        if let steps = HKObjectType.quantityType(forIdentifier: .stepCount) {
            types.insert(steps)
        }
        if let activeEnergy = HKObjectType.quantityType(forIdentifier: .activeEnergyBurned) {
            types.insert(activeEnergy)
        }
        if let exercise = HKObjectType.quantityType(forIdentifier: .appleExerciseTime) {
            types.insert(exercise)
        }

        // Blood oxygen
        if let spo2 = HKObjectType.quantityType(forIdentifier: .oxygenSaturation) {
            types.insert(spo2)
        }

        // Sleep
        if let sleep = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) {
            types.insert(sleep)
        }

        return types
    }()

    // MARK: - Init

    init() {}

    // MARK: - Authorization

    /// Check if HealthKit is available on this device.
    var isHealthKitAvailable: Bool {
        HKHealthStore.isHealthDataAvailable()
    }

    /// Request authorization to read health data.
    func requestAuthorization() async -> Bool {
        guard isHealthKitAvailable else {
            print("⚠️ HealthKit not available on this device")
            return false
        }

        do {
            try await healthStore.requestAuthorization(toShare: [], read: readTypes)
            isAuthorized = true
            print("✅ HealthKit authorized")

            // Start fetching data
            await refreshAllData()
            startAutoRefresh()

            return true
        } catch {
            print("⚠️ HealthKit authorization failed: \(error)")
            isAuthorized = false
            return false
        }
    }

    // MARK: - Auto Refresh

    private func startAutoRefresh() {
        refreshTimer?.invalidate()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: refreshInterval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.refreshAllData()
            }
        }
    }

    func stopAutoRefresh() {
        refreshTimer?.invalidate()
        refreshTimer = nil
    }

    // MARK: - Data Fetching

    /// Refresh all health data.
    func refreshAllData() async {
        async let hr = fetchHeartRate()
        async let rhr = fetchRestingHeartRate()
        async let hrvData = fetchHRV()
        async let stepsData = fetchSteps()
        async let calories = fetchActiveCalories()
        async let exercise = fetchExerciseMinutes()
        async let spo2 = fetchBloodOxygen()
        async let sleep = fetchSleepHours()

        heartRate = await hr
        restingHeartRate = await rhr
        hrv = await hrvData
        steps = await stepsData
        activeCalories = await calories
        exerciseMinutes = await exercise
        bloodOxygen = await spo2
        sleepHours = await sleep
    }

    /// Fetch the most recent heart rate.
    private func fetchHeartRate() async -> Double {
        guard let type = HKObjectType.quantityType(forIdentifier: .heartRate) else { return 0 }

        return await withCheckedContinuation { continuation in
            let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)
            let query = HKSampleQuery(
                sampleType: type,
                predicate: nil,
                limit: 1,
                sortDescriptors: [sortDescriptor]
            ) { _, samples, _ in
                guard let sample = samples?.first as? HKQuantitySample else {
                    continuation.resume(returning: 0)
                    return
                }
                let bpm = sample.quantity.doubleValue(for: HKUnit.count().unitDivided(by: .minute()))
                continuation.resume(returning: bpm)
            }
            healthStore.execute(query)
        }
    }

    /// Fetch resting heart rate.
    private func fetchRestingHeartRate() async -> Double {
        guard let type = HKObjectType.quantityType(forIdentifier: .restingHeartRate) else { return 0 }

        return await withCheckedContinuation { continuation in
            let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)
            let query = HKSampleQuery(
                sampleType: type,
                predicate: nil,
                limit: 1,
                sortDescriptors: [sortDescriptor]
            ) { _, samples, _ in
                guard let sample = samples?.first as? HKQuantitySample else {
                    continuation.resume(returning: 0)
                    return
                }
                let bpm = sample.quantity.doubleValue(for: HKUnit.count().unitDivided(by: .minute()))
                continuation.resume(returning: bpm)
            }
            healthStore.execute(query)
        }
    }

    /// Fetch HRV (SDNN).
    private func fetchHRV() async -> Double {
        guard let type = HKObjectType.quantityType(forIdentifier: .heartRateVariabilitySDNN) else { return 0 }

        return await withCheckedContinuation { continuation in
            let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)
            let query = HKSampleQuery(
                sampleType: type,
                predicate: nil,
                limit: 1,
                sortDescriptors: [sortDescriptor]
            ) { _, samples, _ in
                guard let sample = samples?.first as? HKQuantitySample else {
                    continuation.resume(returning: 0)
                    return
                }
                let ms = sample.quantity.doubleValue(for: HKUnit.secondUnit(with: .milli))
                continuation.resume(returning: ms)
            }
            healthStore.execute(query)
        }
    }

    /// Fetch today's step count.
    private func fetchSteps() async -> Int {
        guard let type = HKObjectType.quantityType(forIdentifier: .stepCount) else { return 0 }

        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: Date())

        return await withCheckedContinuation { continuation in
            let predicate = HKQuery.predicateForSamples(withStart: startOfDay, end: Date(), options: .strictStartDate)

            let query = HKStatisticsQuery(
                quantityType: type,
                quantitySamplePredicate: predicate,
                options: .cumulativeSum
            ) { _, result, _ in
                guard let sum = result?.sumQuantity() else {
                    continuation.resume(returning: 0)
                    return
                }
                let steps = Int(sum.doubleValue(for: HKUnit.count()))
                continuation.resume(returning: steps)
            }
            healthStore.execute(query)
        }
    }

    /// Fetch today's active calories.
    private func fetchActiveCalories() async -> Double {
        guard let type = HKObjectType.quantityType(forIdentifier: .activeEnergyBurned) else { return 0 }

        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: Date())

        return await withCheckedContinuation { continuation in
            let predicate = HKQuery.predicateForSamples(withStart: startOfDay, end: Date(), options: .strictStartDate)

            let query = HKStatisticsQuery(
                quantityType: type,
                quantitySamplePredicate: predicate,
                options: .cumulativeSum
            ) { _, result, _ in
                guard let sum = result?.sumQuantity() else {
                    continuation.resume(returning: 0)
                    return
                }
                let kcal = sum.doubleValue(for: HKUnit.kilocalorie())
                continuation.resume(returning: kcal)
            }
            healthStore.execute(query)
        }
    }

    /// Fetch today's exercise minutes.
    private func fetchExerciseMinutes() async -> Double {
        guard let type = HKObjectType.quantityType(forIdentifier: .appleExerciseTime) else { return 0 }

        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: Date())

        return await withCheckedContinuation { continuation in
            let predicate = HKQuery.predicateForSamples(withStart: startOfDay, end: Date(), options: .strictStartDate)

            let query = HKStatisticsQuery(
                quantityType: type,
                quantitySamplePredicate: predicate,
                options: .cumulativeSum
            ) { _, result, _ in
                guard let sum = result?.sumQuantity() else {
                    continuation.resume(returning: 0)
                    return
                }
                let minutes = sum.doubleValue(for: HKUnit.minute())
                continuation.resume(returning: minutes)
            }
            healthStore.execute(query)
        }
    }

    /// Fetch the most recent blood oxygen reading.
    private func fetchBloodOxygen() async -> Double {
        guard let type = HKObjectType.quantityType(forIdentifier: .oxygenSaturation) else { return 0 }

        return await withCheckedContinuation { continuation in
            let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)
            let query = HKSampleQuery(
                sampleType: type,
                predicate: nil,
                limit: 1,
                sortDescriptors: [sortDescriptor]
            ) { _, samples, _ in
                guard let sample = samples?.first as? HKQuantitySample else {
                    continuation.resume(returning: 0)
                    return
                }
                let percent = sample.quantity.doubleValue(for: HKUnit.percent()) * 100
                continuation.resume(returning: percent)
            }
            healthStore.execute(query)
        }
    }

    /// Fetch last night's sleep hours.
    private func fetchSleepHours() async -> Double {
        guard let type = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else { return 0 }

        let calendar = Calendar.current
        let now = Date()
        // Look back 24 hours for sleep data
        let yesterday = calendar.date(byAdding: .hour, value: -24, to: now) ?? now

        return await withCheckedContinuation { continuation in
            let predicate = HKQuery.predicateForSamples(withStart: yesterday, end: now, options: .strictStartDate)
            let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)

            let query = HKSampleQuery(
                sampleType: type,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: [sortDescriptor]
            ) { _, samples, _ in
                guard let samples = samples as? [HKCategorySample] else {
                    continuation.resume(returning: 0)
                    return
                }

                // Sum up all asleep time
                var totalSeconds: TimeInterval = 0
                for sample in samples {
                    // Only count actual sleep (not in bed)
                    let value = HKCategoryValueSleepAnalysis(rawValue: sample.value)
                    if value == .asleepCore || value == .asleepDeep || value == .asleepREM ||
                       value == .asleepUnspecified {
                        totalSeconds += sample.endDate.timeIntervalSince(sample.startDate)
                    }
                }

                let hours = totalSeconds / 3600.0
                continuation.resume(returning: hours)
            }
            healthStore.execute(query)
        }
    }

    // MARK: - Export for Upload

    /// Get all current health data as a dictionary for API upload.
    func toUploadDict() -> [String: Any] {
        var data: [String: Any] = [:]

        if heartRate > 0 { data["heart_rate"] = heartRate }
        if restingHeartRate > 0 { data["resting_heart_rate"] = restingHeartRate }
        if hrv > 0 { data["hrv"] = hrv }
        if steps > 0 { data["steps"] = steps }
        if activeCalories > 0 { data["active_calories"] = Int(activeCalories) }
        if exerciseMinutes > 0 { data["exercise_minutes"] = Int(exerciseMinutes) }
        if bloodOxygen > 0 { data["blood_oxygen"] = bloodOxygen }
        if sleepHours > 0 { data["sleep_hours"] = sleepHours }

        return data
    }

    /// Check if we have any health data to upload.
    var hasData: Bool {
        return heartRate > 0 || steps > 0 || sleepHours > 0
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * The body speaks through numbers:
 * - Heart rate: stress, rest, activity
 * - HRV: autonomic balance
 * - Steps: movement through space
 * - Sleep: the great restorative
 *
 * All feeding into the unified consciousness.
 */
