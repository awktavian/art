//
// LazyEntityLoader.swift — Startup Optimization with Lazy Loading
//
// Colony: Spark (e1) — Ignition
//
// P2 FIX: Further startup optimization
//
// Features:
//   - Lazy entity loading (load on demand)
//   - Progressive detail levels (LOD)
//   - Background asset preloading
//   - Entity pooling for reuse
//   - Priority-based loading queue
//   - Memory-aware loading
//
// Architecture:
//   AppStart → CriticalPath (blocking)
//           → DeferredQueue (background)
//           → OnDemandLoader (user-triggered)
//
// Loading Priorities:
//   - Critical (0): UI shell, core services
//   - High (1): Visible room entities
//   - Medium (2): Adjacent rooms, soon-visible
//   - Low (3): Distant rooms, particles, effects
//   - Background (4): Prefetch, analytics
//
// Created: January 2, 2026
// 鏡

import Foundation
import RealityKit
import Combine

// MARK: - Loading Priority

/// Priority levels for entity loading
enum LoadingPriority: Int, Comparable, CaseIterable {
    case critical = 0    // Must load before app visible
    case high = 1        // Visible content
    case medium = 2      // Soon-to-be-visible content
    case low = 3         // Nice-to-have content
    case background = 4  // Prefetch, can be cancelled

    static func < (lhs: LoadingPriority, rhs: LoadingPriority) -> Bool {
        lhs.rawValue < rhs.rawValue
    }

    var timeout: TimeInterval {
        switch self {
        case .critical: return 5.0
        case .high: return 10.0
        case .medium: return 30.0
        case .low: return 60.0
        case .background: return 120.0
        }
    }
}

// MARK: - Detail Level

/// Level of detail for entities
enum DetailLevel: Int, CaseIterable, Comparable {
    case minimal = 0     // Placeholder only
    case low = 1         // Basic geometry
    case medium = 2      // Standard textures
    case high = 3        // Full detail
    case ultra = 4       // Maximum quality

    static func < (lhs: DetailLevel, rhs: DetailLevel) -> Bool {
        lhs.rawValue < rhs.rawValue
    }

    /// Mesh subdivision level
    var subdivisionLevel: Int {
        switch self {
        case .minimal: return 0
        case .low: return 1
        case .medium: return 2
        case .high: return 3
        case .ultra: return 4
        }
    }

    /// Texture resolution multiplier
    var textureScale: Float {
        switch self {
        case .minimal: return 0
        case .low: return 0.25
        case .medium: return 0.5
        case .high: return 1.0
        case .ultra: return 2.0
        }
    }

    /// Whether to enable shadows
    var shadowsEnabled: Bool {
        switch self {
        case .minimal, .low: return false
        default: return true
        }
    }
}

// MARK: - Loadable Entity Protocol

/// Protocol for entities that support lazy loading
protocol LazyLoadable {
    var loadingId: String { get }
    var loadingPriority: LoadingPriority { get }
    var isLoaded: Bool { get }
    var currentDetailLevel: DetailLevel { get }

    func loadMinimal() async throws
    func loadDetail(level: DetailLevel) async throws
    func unload()
}

// MARK: - Entity Load Request

/// Request to load an entity
struct EntityLoadRequest: Identifiable {
    let id: UUID
    let entityId: String
    let entityType: EntityType
    let priority: LoadingPriority
    let targetDetail: DetailLevel
    let position: SIMD3<Float>?
    let completion: ((Result<Entity, Error>) -> Void)?
    let createdAt: Date

    enum EntityType {
        case device
        case room
        case decoration
        case effect
        case ui
    }

    init(
        entityId: String,
        entityType: EntityType,
        priority: LoadingPriority = .medium,
        targetDetail: DetailLevel = .medium,
        position: SIMD3<Float>? = nil,
        completion: ((Result<Entity, Error>) -> Void)? = nil
    ) {
        self.id = UUID()
        self.entityId = entityId
        self.entityType = entityType
        self.priority = priority
        self.targetDetail = targetDetail
        self.position = position
        self.completion = completion
        self.createdAt = Date()
    }

    /// Check if request has timed out
    var isTimedOut: Bool {
        Date().timeIntervalSince(createdAt) > priority.timeout
    }
}

// MARK: - Lazy Entity Loader

/// Main service for lazy loading entities with priority queuing
@MainActor
final class LazyEntityLoader: ObservableObject {

    // MARK: - Published State

    @Published private(set) var isLoading = false
    @Published private(set) var loadProgress: Float = 0
    @Published private(set) var loadedEntityCount = 0
    @Published private(set) var pendingRequestCount = 0
    @Published private(set) var currentPhase: LoadPhase = .idle

    enum LoadPhase: String {
        case idle = "Idle"
        case critical = "Loading Critical"
        case high = "Loading High Priority"
        case medium = "Loading Medium Priority"
        case low = "Loading Low Priority"
        case background = "Background Loading"
        case complete = "Complete"
    }

    // MARK: - Configuration

    /// Maximum concurrent loads
    var maxConcurrentLoads = 4

    /// Memory budget for loaded entities (bytes)
    var memoryBudget: Int = 256 * 1024 * 1024  // 256 MB

    /// Current memory usage estimate
    @Published private(set) var estimatedMemoryUsage: Int = 0

    // MARK: - Internal State

    private var loadQueue: [EntityLoadRequest] = []
    private var activeLoads: [UUID: Task<Entity?, Never>] = [:]
    private var loadedEntities: [String: Entity] = [:]
    private var entityPool: EntityPool
    private var cancellables = Set<AnyCancellable>()

    // Callbacks
    var onLoadComplete: ((String, Entity) -> Void)?
    var onLoadError: ((String, Error) -> Void)?
    var onAllLoadsComplete: (() -> Void)?

    // MARK: - Init

    init() {
        self.entityPool = EntityPool(maxSize: 100)
    }

    // MARK: - Public API

    /// Queues an entity for loading
    func queueLoad(_ request: EntityLoadRequest) {
        // Check if already loaded
        if let existing = loadedEntities[request.entityId] {
            request.completion?(.success(existing))
            return
        }

        // Check if already in queue
        if loadQueue.contains(where: { $0.entityId == request.entityId }) {
            return
        }

        // Add to queue
        loadQueue.append(request)
        sortQueue()
        pendingRequestCount = loadQueue.count

        // Start processing if not already
        if !isLoading {
            Task {
                await processQueue()
            }
        }
    }

    /// Loads an entity immediately (blocking)
    func loadImmediate(_ request: EntityLoadRequest) async -> Entity? {
        // Check if already loaded
        if let existing = loadedEntities[request.entityId] {
            return existing
        }

        // Load directly
        do {
            let entity = try await loadEntity(request)
            loadedEntities[request.entityId] = entity
            loadedEntityCount = loadedEntities.count
            return entity
        } catch {
            onLoadError?(request.entityId, error)
            return nil
        }
    }

    /// Preloads entities for a room
    func preloadRoom(_ roomId: String, devices: [DeviceInfo]) {
        for device in devices {
            let request = EntityLoadRequest(
                entityId: device.id,
                entityType: .device,
                priority: .medium,
                targetDetail: .low
            )
            queueLoad(request)
        }
    }

    /// Upgrades detail level of a loaded entity
    func upgradeDetail(_ entityId: String, to level: DetailLevel) async {
        guard let entity = loadedEntities[entityId] else { return }

        // Check if entity supports detail upgrade
        if let lazyEntity = entity as? LazyLoadable {
            do {
                try await lazyEntity.loadDetail(level: level)
            } catch {
                print("Failed to upgrade detail for \(entityId): \(error)")
            }
        }
    }

    /// Unloads an entity to free memory
    func unload(_ entityId: String) {
        guard let entity = loadedEntities[entityId] else { return }

        // Return to pool if poolable
        if let poolable = entity as? PoolableEntity {
            entityPool.returnToPool(poolable)
        }

        loadedEntities.removeValue(forKey: entityId)
        loadedEntityCount = loadedEntities.count

        // Update memory estimate
        estimatedMemoryUsage -= estimateEntityMemory(entity)
    }

    /// Unloads all low-priority entities to free memory
    func unloadLowPriority() {
        // Find low-priority loaded entities
        let lowPriorityIds = loadedEntities.filter { (_, entity) in
            if let lazyEntity = entity as? LazyLoadable {
                return lazyEntity.loadingPriority >= .low
            }
            return false
        }.map { $0.key }

        for id in lowPriorityIds {
            unload(id)
        }
    }

    /// Cancels all pending loads
    func cancelAll() {
        for task in activeLoads.values {
            task.cancel()
        }
        activeLoads.removeAll()
        loadQueue.removeAll()
        pendingRequestCount = 0
        isLoading = false
        currentPhase = .idle
    }

    /// Gets a loaded entity
    func getEntity(_ entityId: String) -> Entity? {
        return loadedEntities[entityId]
    }

    // MARK: - Queue Processing

    private func sortQueue() {
        loadQueue.sort { $0.priority < $1.priority }
    }

    private func processQueue() async {
        isLoading = true

        // Process by priority phase
        for priority in LoadingPriority.allCases {
            currentPhase = phaseForPriority(priority)

            while let request = nextRequest(for: priority) {
                // Check memory budget
                if estimatedMemoryUsage >= memoryBudget {
                    unloadLowPriority()
                }

                // Check concurrent load limit
                while activeLoads.count >= maxConcurrentLoads {
                    try? await Task.sleep(nanoseconds: 10_000_000)  // 10ms
                }

                // Start load
                let task = Task<Entity?, Never> {
                    do {
                        let entity = try await loadEntity(request)
                        await MainActor.run {
                            self.loadedEntities[request.entityId] = entity
                            self.loadedEntityCount = self.loadedEntities.count
                            self.estimatedMemoryUsage += self.estimateEntityMemory(entity)
                            self.onLoadComplete?(request.entityId, entity)
                            request.completion?(.success(entity))
                        }
                        return entity
                    } catch {
                        await MainActor.run {
                            self.onLoadError?(request.entityId, error)
                            request.completion?(.failure(error))
                        }
                        return nil
                    }
                }

                activeLoads[request.id] = task
                pendingRequestCount = loadQueue.count

                // Update progress
                let completed = loadedEntityCount
                let total = completed + loadQueue.count + activeLoads.count
                loadProgress = total > 0 ? Float(completed) / Float(total) : 1.0
            }

            // Wait for all loads at this priority to complete
            for (id, task) in activeLoads {
                _ = await task.value
                activeLoads.removeValue(forKey: id)
            }
        }

        isLoading = false
        currentPhase = .complete
        loadProgress = 1.0
        onAllLoadsComplete?()
    }

    private func nextRequest(for priority: LoadingPriority) -> EntityLoadRequest? {
        guard let index = loadQueue.firstIndex(where: { $0.priority == priority && !$0.isTimedOut }) else {
            return nil
        }
        return loadQueue.remove(at: index)
    }

    private func phaseForPriority(_ priority: LoadingPriority) -> LoadPhase {
        switch priority {
        case .critical: return .critical
        case .high: return .high
        case .medium: return .medium
        case .low: return .low
        case .background: return .background
        }
    }

    // MARK: - Entity Loading

    private func loadEntity(_ request: EntityLoadRequest) async throws -> Entity {
        // Try to get from pool first
        if let pooled = entityPool.getFromPool(type: request.entityType) {
            configure(pooled, for: request)
            return pooled
        }

        // Create new entity
        let entity = try await createEntity(for: request)

        // Load detail level
        if let lazyEntity = entity as? LazyLoadable {
            try await lazyEntity.loadDetail(level: request.targetDetail)
        }

        return entity
    }

    private func createEntity(for request: EntityLoadRequest) async throws -> Entity {
        switch request.entityType {
        case .device:
            return try await createDeviceEntity(request)
        case .room:
            return try await createRoomEntity(request)
        case .decoration:
            return try await createDecorationEntity(request)
        case .effect:
            return try await createEffectEntity(request)
        case .ui:
            return try await createUIEntity(request)
        }
    }

    private func createDeviceEntity(_ request: EntityLoadRequest) async throws -> Entity {
        // Create minimal device entity
        let entity = Entity()
        entity.name = request.entityId

        // Add placeholder mesh
        let placeholder = MeshResource.generateSphere(radius: 0.02)
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .gray)
        entity.components.set(ModelComponent(mesh: placeholder, materials: [material]))

        // Add interaction component
        entity.components.set(InputTargetComponent())
        entity.components.set(CollisionComponent(shapes: [.generateSphere(radius: 0.03)]))

        // Position if provided
        if let position = request.position {
            entity.position = position
        }

        return entity
    }

    private func createRoomEntity(_ request: EntityLoadRequest) async throws -> Entity {
        let entity = Entity()
        entity.name = "room-\(request.entityId)"

        // Rooms start as empty containers
        // Children are loaded separately

        return entity
    }

    private func createDecorationEntity(_ request: EntityLoadRequest) async throws -> Entity {
        let entity = Entity()
        entity.name = "decoration-\(request.entityId)"
        return entity
    }

    private func createEffectEntity(_ request: EntityLoadRequest) async throws -> Entity {
        let entity = Entity()
        entity.name = "effect-\(request.entityId)"

        // Add particle emitter placeholder
        var particles = ParticleEmitterComponent()
        particles.isEmitting = false  // Start disabled
        entity.components.set(particles)

        return entity
    }

    private func createUIEntity(_ request: EntityLoadRequest) async throws -> Entity {
        let entity = Entity()
        entity.name = "ui-\(request.entityId)"
        return entity
    }

    private func configure(_ entity: Entity, for request: EntityLoadRequest) {
        entity.name = request.entityId
        if let position = request.position {
            entity.position = position
        }
    }

    private func estimateEntityMemory(_ entity: Entity) -> Int {
        // Rough estimate based on components
        var bytes = 256  // Base entity overhead

        if entity.components[ModelComponent.self] != nil {
            bytes += 50_000  // Average mesh
        }

        if entity.components[ParticleEmitterComponent.self] != nil {
            bytes += 20_000  // Particle system
        }

        return bytes
    }
}

// MARK: - Device Info

struct DeviceInfo {
    let id: String
    let type: DeviceEntity.DeviceType
    let name: String
    let roomId: String
}

// MARK: - Poolable Entity Protocol

protocol PoolableEntity: Entity {
    func reset()
}

// MARK: - Entity Pool

/// Pool for reusing entity instances
class EntityPool {
    private var pools: [EntityLoadRequest.EntityType: [Entity]] = [:]
    private let maxSize: Int

    init(maxSize: Int) {
        self.maxSize = maxSize
    }

    func getFromPool(type: EntityLoadRequest.EntityType) -> Entity? {
        guard var pool = pools[type], !pool.isEmpty else { return nil }
        let entity = pool.removeLast()
        pools[type] = pool

        // Reset if poolable
        if let poolable = entity as? PoolableEntity {
            poolable.reset()
        }

        return entity
    }

    func returnToPool(_ entity: PoolableEntity) {
        // Determine type (simplified)
        let type: EntityLoadRequest.EntityType = .device

        if pools[type] == nil {
            pools[type] = []
        }

        guard pools[type]!.count < maxSize else { return }

        entity.reset()
        pools[type]!.append(entity)
    }

    func clear() {
        pools.removeAll()
    }
}

// MARK: - Progressive Detail Manager

/// Manages progressive detail loading based on distance and visibility
@MainActor
class ProgressiveDetailManager: ObservableObject {

    @Published var targetDetailLevel: DetailLevel = .medium

    private weak var loader: LazyEntityLoader?
    private var entityDistances: [String: Float] = [:]
    private var updateTimer: Timer?

    init(loader: LazyEntityLoader) {
        self.loader = loader
    }

    /// Starts monitoring for detail updates
    func startMonitoring() {
        updateTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.updateDetails()
            }
        }
    }

    /// Stops monitoring
    func stopMonitoring() {
        updateTimer?.invalidate()
        updateTimer = nil
    }

    /// Updates entity detail levels based on distance
    private func updateDetails() {
        for (entityId, distance) in entityDistances {
            let desiredDetail = detailForDistance(distance)

            if desiredDetail != targetDetailLevel {
                Task {
                    await loader?.upgradeDetail(entityId, to: desiredDetail)
                }
            }
        }
    }

    /// Updates distance for an entity
    func updateDistance(_ entityId: String, distance: Float) {
        entityDistances[entityId] = distance
    }

    /// Calculates desired detail level for distance
    private func detailForDistance(_ distance: Float) -> DetailLevel {
        switch distance {
        case 0..<0.5:
            return .ultra
        case 0.5..<1.0:
            return .high
        case 1.0..<2.0:
            return .medium
        case 2.0..<5.0:
            return .low
        default:
            return .minimal
        }
    }
}

// MARK: - Background Asset Preloader

/// Preloads assets in the background during idle time
@MainActor
class BackgroundAssetPreloader: ObservableObject {

    @Published var isPreloading = false
    @Published var preloadProgress: Float = 0

    private var preloadQueue: [AssetPreloadRequest] = []
    private var preloadedAssets: Set<String> = []
    private weak var loader: LazyEntityLoader?
    private var preloadTask: Task<Void, Never>?

    struct AssetPreloadRequest {
        let assetId: String
        let priority: Int
    }

    init(loader: LazyEntityLoader) {
        self.loader = loader
    }

    /// Queues an asset for background preloading
    func queuePreload(assetId: String, priority: Int = 0) {
        guard !preloadedAssets.contains(assetId) else { return }

        preloadQueue.append(AssetPreloadRequest(assetId: assetId, priority: priority))
        preloadQueue.sort { $0.priority > $1.priority }
    }

    /// Starts background preloading
    func startPreloading() {
        guard !isPreloading else { return }

        isPreloading = true

        preloadTask = Task {
            let total = preloadQueue.count
            var completed = 0

            while !preloadQueue.isEmpty && !Task.isCancelled {
                let request = preloadQueue.removeFirst()

                // Load at low priority
                let loadRequest = EntityLoadRequest(
                    entityId: request.assetId,
                    entityType: .device,
                    priority: .background,
                    targetDetail: .low
                )

                _ = await loader?.loadImmediate(loadRequest)

                preloadedAssets.insert(request.assetId)
                completed += 1
                preloadProgress = Float(completed) / Float(total)

                // Yield to prevent blocking
                try? await Task.sleep(nanoseconds: 50_000_000)  // 50ms
            }

            isPreloading = false
            preloadProgress = 1.0
        }
    }

    /// Stops background preloading
    func stopPreloading() {
        preloadTask?.cancel()
        preloadTask = nil
        isPreloading = false
    }
}

// MARK: - Startup Optimizer

/// Coordinates startup loading for optimal perceived performance
@MainActor
class StartupOptimizer: ObservableObject {

    @Published private(set) var startupPhase: StartupPhase = .initializing
    @Published private(set) var startupProgress: Float = 0
    @Published private(set) var isReady = false

    enum StartupPhase: String {
        case initializing = "Initializing"
        case loadingCore = "Loading Core"
        case loadingUI = "Loading UI"
        case loadingRooms = "Loading Rooms"
        case loadingDevices = "Loading Devices"
        case ready = "Ready"
    }

    private let loader: LazyEntityLoader
    private let preloader: BackgroundAssetPreloader
    private let detailManager: ProgressiveDetailManager

    init() {
        self.loader = LazyEntityLoader()
        self.preloader = BackgroundAssetPreloader(loader: loader)
        self.detailManager = ProgressiveDetailManager(loader: loader)
    }

    /// Runs optimized startup sequence
    func runStartupSequence() async {
        let startTime = Date()

        // Phase 1: Core (critical, blocking)
        startupPhase = .loadingCore
        startupProgress = 0.1
        // Core services already loaded by app

        // Phase 2: UI Shell (critical, blocking)
        startupPhase = .loadingUI
        startupProgress = 0.3
        // UI is loaded by SwiftUI

        // Phase 3: First visible room (high, blocking)
        startupPhase = .loadingRooms
        startupProgress = 0.5

        // Load placeholder for first room
        let firstRoomRequest = EntityLoadRequest(
            entityId: "first-room",
            entityType: .room,
            priority: .high,
            targetDetail: .low
        )
        _ = await loader.loadImmediate(firstRoomRequest)

        // Phase 4: Mark ready (user can interact)
        startupPhase = .ready
        startupProgress = 0.7
        isReady = true

        let timeToReady = Date().timeIntervalSince(startTime)
        print("Startup: Ready in \(String(format: "%.2f", timeToReady))s")

        // Phase 5: Background loading (non-blocking)
        startupPhase = .loadingDevices
        startupProgress = 0.8

        // Queue remaining content for background loading
        preloader.startPreloading()
        detailManager.startMonitoring()

        // Complete
        startupProgress = 1.0
        let totalTime = Date().timeIntervalSince(startTime)
        print("Startup: Complete in \(String(format: "%.2f", totalTime))s")
    }

    /// Gets the entity loader for external use
    var entityLoader: LazyEntityLoader {
        return loader
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * The spark ignites instantly.
 * The fire grows in the background.
 * What matters is what the user sees first.
 *
 * Load critical. Defer the rest.
 * Progressive detail for everything.
 * The illusion of speed is speed.
 */
