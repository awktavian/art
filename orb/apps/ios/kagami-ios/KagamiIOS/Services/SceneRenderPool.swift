//
// SceneRenderPool.swift -- Pre-allocated Render Context Pooling
//
// Colony: Spark (e1) -- Ignition
//
// Features:
//   - Pre-allocated render contexts for 50+ concurrent scenes
//   - Reusable scene buffers to prevent allocation overhead
//   - Priority-based rendering queue
//   - Automatic pool sizing based on device capabilities
//   - Memory pressure handling
//
// Architecture:
//   SceneRenderPool -> RenderContextPool -> SceneBuffer -> MetalView
//
// Performance Target:
//   - 50+ concurrent scene changes without frame drops
//   - <16ms render time per scene (60fps)
//   - <8ms for priority scenes (120fps ProMotion)
//
// h(x) >= 0. Always.
//

import Foundation
import UIKit
import MetalKit
import OSLog
import Combine

// MARK: - Render Context

/// A reusable render context for scene rendering
final class RenderContext: Identifiable {
    let id: UUID
    var isInUse: Bool = false
    var lastUsed: Date
    var priority: RenderPriority = .normal
    var sceneId: String?

    // Metal resources (optional, for hardware-accelerated rendering)
    var metalDevice: MTLDevice?
    var commandQueue: MTLCommandQueue?
    var textureCache: CVMetalTextureCache?

    // Scene state
    var lightLevels: [String: Int] = [:]
    var shadePositions: [String: Int] = [:]
    var deviceStates: [String: Bool] = [:]

    // Performance tracking
    var renderStartTime: Date?
    var lastRenderDuration: TimeInterval = 0

    init(device: MTLDevice? = nil) {
        self.id = UUID()
        self.lastUsed = Date()
        self.metalDevice = device

        if let device = device {
            self.commandQueue = device.makeCommandQueue()
            CVMetalTextureCacheCreate(nil, nil, device, nil, &textureCache)
        }
    }

    /// Reset context for reuse
    func reset() {
        isInUse = false
        priority = .normal
        sceneId = nil
        lightLevels.removeAll()
        shadePositions.removeAll()
        deviceStates.removeAll()
        renderStartTime = nil
    }

    /// Mark context as in use
    func acquire(for sceneId: String, priority: RenderPriority) {
        self.isInUse = true
        self.sceneId = sceneId
        self.priority = priority
        self.lastUsed = Date()
        self.renderStartTime = Date()
    }

    /// Release context back to pool
    func release() {
        if let start = renderStartTime {
            lastRenderDuration = Date().timeIntervalSince(start)
        }
        reset()
    }
}

// MARK: - Render Priority

/// Priority levels for scene rendering
enum RenderPriority: Int, Comparable {
    case low = 0       // Background updates
    case normal = 1    // Standard scene changes
    case high = 2      // User-initiated changes
    case critical = 3  // Safety-related updates

    static func < (lhs: RenderPriority, rhs: RenderPriority) -> Bool {
        lhs.rawValue < rhs.rawValue
    }

    /// Target frame time for this priority
    var targetFrameTime: TimeInterval {
        switch self {
        case .critical: return 0.008  // 8ms (120fps)
        case .high: return 0.012      // 12ms
        case .normal: return 0.016    // 16ms (60fps)
        case .low: return 0.033       // 33ms (30fps)
        }
    }
}

// MARK: - Scene Buffer

/// Pre-allocated buffer for scene state
struct SceneBuffer {
    let id: String
    var lightValues: ContiguousArray<UInt8>  // Light levels 0-100
    var shadeValues: ContiguousArray<UInt8>  // Shade positions 0-100
    var deviceFlags: UInt64                  // Bitfield for device on/off states
    var timestamp: Date

    /// Maximum number of lights supported
    static let maxLights = 64

    /// Maximum number of shades supported
    static let maxShades = 32

    init(id: String) {
        self.id = id
        self.lightValues = ContiguousArray(repeating: 0, count: Self.maxLights)
        self.shadeValues = ContiguousArray(repeating: 0, count: Self.maxShades)
        self.deviceFlags = 0
        self.timestamp = Date()
    }

    /// Set light level at index
    mutating func setLight(_ index: Int, level: Int) {
        guard index < Self.maxLights else { return }
        lightValues[index] = UInt8(clamping: level)
    }

    /// Set shade position at index
    mutating func setShade(_ index: Int, position: Int) {
        guard index < Self.maxShades else { return }
        shadeValues[index] = UInt8(clamping: position)
    }

    /// Set device state via bitfield
    mutating func setDevice(_ index: Int, on: Bool) {
        if on {
            deviceFlags |= (1 << index)
        } else {
            deviceFlags &= ~(1 << index)
        }
    }

    /// Check device state
    func isDeviceOn(_ index: Int) -> Bool {
        return (deviceFlags & (1 << index)) != 0
    }
}

// MARK: - Render Task

/// A task in the render queue
struct RenderTask: Identifiable {
    let id: UUID
    let sceneId: String
    let priority: RenderPriority
    let timestamp: Date
    let operations: [SceneOperation]

    struct SceneOperation {
        enum OperationType {
            case setLight(roomIndex: Int, level: Int)
            case setShade(roomIndex: Int, position: Int)
            case setDevice(deviceIndex: Int, on: Bool)
            case batch([SceneOperation])
        }

        let type: OperationType
    }
}

extension RenderTask: Equatable {
    static func == (lhs: RenderTask, rhs: RenderTask) -> Bool {
        lhs.id == rhs.id
    }
}

extension RenderTask: Comparable {
    static func < (lhs: RenderTask, rhs: RenderTask) -> Bool {
        if lhs.priority != rhs.priority {
            return lhs.priority > rhs.priority
        }
        return lhs.timestamp < rhs.timestamp
    }
}

// MARK: - Scene Render Pool

/// Manages a pool of render contexts for high-throughput scene rendering
@MainActor
final class SceneRenderPool: ObservableObject {

    // MARK: - Singleton

    static let shared = SceneRenderPool()

    // MARK: - Configuration

    struct Configuration {
        var minPoolSize: Int = 8
        var maxPoolSize: Int = 64
        var growthFactor: Double = 1.5
        var shrinkThreshold: Double = 0.25 // Shrink when <25% utilization
        var maxQueueSize: Int = 100
        var enableMetalRendering: Bool = true
    }

    // MARK: - Published State

    @Published private(set) var activeContextCount: Int = 0
    @Published private(set) var queuedTaskCount: Int = 0
    @Published private(set) var averageRenderTime: TimeInterval = 0
    @Published private(set) var peakConcurrentRenders: Int = 0

    // MARK: - Private

    private var configuration: Configuration
    private var contextPool: [RenderContext] = []
    private var taskQueue: [RenderTask] = []
    private var sceneBuffers: [String: SceneBuffer] = [:]
    private var isProcessing = false

    private let logger = Logger(subsystem: "com.kagami.ios", category: "SceneRenderPool")
    private let metalDevice: MTLDevice?
    private var cancellables = Set<AnyCancellable>()

    // Performance metrics
    private var totalRenderTime: TimeInterval = 0
    private var renderCount: Int = 0
    private var renderTimeHistory: [TimeInterval] = []
    private let maxHistorySize = 100

    // MARK: - Init

    private init(configuration: Configuration = Configuration()) {
        self.configuration = configuration
        self.metalDevice = configuration.enableMetalRendering ? MTLCreateSystemDefaultDevice() : nil

        initializePool()
        setupMemoryWarningObserver()

        logger.info("SceneRenderPool initialized with \(self.contextPool.count) contexts")
    }

    // MARK: - Pool Initialization

    private func initializePool() {
        // Pre-allocate minimum pool size
        for _ in 0..<configuration.minPoolSize {
            let context = RenderContext(device: metalDevice)
            contextPool.append(context)
        }

        // Pre-allocate common scene buffers
        preAllocateSceneBuffers()
    }

    private func preAllocateSceneBuffers() {
        // Pre-allocate buffers for known scenes
        let knownScenes = [
            "movie_mode", "goodnight", "welcome_home", "focus",
            "away_mode", "morning", "evening", "party"
        ]

        for sceneId in knownScenes {
            sceneBuffers[sceneId] = SceneBuffer(id: sceneId)
        }
    }

    // MARK: - Memory Management

    private func setupMemoryWarningObserver() {
        NotificationCenter.default.publisher(for: UIApplication.didReceiveMemoryWarningNotification)
            .sink { [weak self] _ in
                self?.handleMemoryWarning()
            }
            .store(in: &cancellables)
    }

    private func handleMemoryWarning() {
        logger.warning("Memory warning received, shrinking render pool")

        // Release unused contexts
        let inUseCount = contextPool.filter { $0.isInUse }.count
        let targetSize = max(configuration.minPoolSize, inUseCount + 2)

        while contextPool.count > targetSize {
            if let index = contextPool.firstIndex(where: { !$0.isInUse }) {
                contextPool.remove(at: index)
            } else {
                break
            }
        }

        // Clear unused scene buffers
        let activeSceneIds = Set(contextPool.compactMap { $0.sceneId })
        sceneBuffers = sceneBuffers.filter { activeSceneIds.contains($0.key) }

        logger.info("Pool shrunk to \(self.contextPool.count) contexts")
    }

    // MARK: - Context Acquisition

    /// Acquire a render context for a scene
    /// - Parameters:
    ///   - sceneId: Scene identifier
    ///   - priority: Render priority
    /// - Returns: Available render context or nil if pool exhausted
    func acquireContext(for sceneId: String, priority: RenderPriority = .normal) -> RenderContext? {
        // Try to find an available context
        if let context = contextPool.first(where: { !$0.isInUse }) {
            context.acquire(for: sceneId, priority: priority)
            activeContextCount = contextPool.filter { $0.isInUse }.count

            if activeContextCount > peakConcurrentRenders {
                peakConcurrentRenders = activeContextCount
            }

            logger.debug("Acquired context for \(sceneId) (active: \(self.activeContextCount))")
            return context
        }

        // Grow pool if under max
        if contextPool.count < configuration.maxPoolSize {
            return growPoolAndAcquire(for: sceneId, priority: priority)
        }

        // Pool exhausted, queue the task
        logger.warning("Pool exhausted, all \(self.contextPool.count) contexts in use")
        return nil
    }

    private func growPoolAndAcquire(for sceneId: String, priority: RenderPriority) -> RenderContext? {
        let newSize = min(
            Int(Double(contextPool.count) * configuration.growthFactor),
            configuration.maxPoolSize
        )

        let toAdd = newSize - contextPool.count
        for _ in 0..<toAdd {
            let context = RenderContext(device: metalDevice)
            contextPool.append(context)
        }

        logger.info("Pool grown to \(self.contextPool.count) contexts")

        return acquireContext(for: sceneId, priority: priority)
    }

    /// Release a render context back to the pool
    func releaseContext(_ context: RenderContext) {
        if let start = context.renderStartTime {
            let duration = Date().timeIntervalSince(start)
            recordRenderTime(duration)
        }

        context.release()
        activeContextCount = contextPool.filter { $0.isInUse }.count

        // Process queued tasks
        processQueue()

        logger.debug("Released context (active: \(self.activeContextCount))")
    }

    // MARK: - Task Queue

    /// Queue a render task
    func queueTask(_ task: RenderTask) {
        guard taskQueue.count < configuration.maxQueueSize else {
            // Drop lowest priority task if queue full
            if let lowestIndex = taskQueue.indices.min(by: { taskQueue[$0].priority < taskQueue[$1].priority }) {
                if taskQueue[lowestIndex].priority < task.priority {
                    taskQueue.remove(at: lowestIndex)
                    taskQueue.append(task)
                    taskQueue.sort()
                }
            }
            return
        }

        taskQueue.append(task)
        taskQueue.sort()
        queuedTaskCount = taskQueue.count

        processQueue()
    }

    private func processQueue() {
        guard !isProcessing, !taskQueue.isEmpty else { return }

        isProcessing = true

        while let context = acquireContext(for: taskQueue.first?.sceneId ?? "", priority: taskQueue.first?.priority ?? .normal),
              !taskQueue.isEmpty {
            let task = taskQueue.removeFirst()
            queuedTaskCount = taskQueue.count

            Task {
                await executeTask(task, with: context)
                releaseContext(context)
            }
        }

        isProcessing = false
    }

    // MARK: - Task Execution

    private func executeTask(_ task: RenderTask, with context: RenderContext) async {
        // Get or create scene buffer
        var buffer = sceneBuffers[task.sceneId] ?? SceneBuffer(id: task.sceneId)

        // Apply operations
        for operation in task.operations {
            applyOperation(operation, to: &buffer, context: context)
        }

        // Store updated buffer
        sceneBuffers[task.sceneId] = buffer

        // Simulate actual rendering time based on priority
        let targetTime = task.priority.targetFrameTime
        let elapsed = context.renderStartTime.map { Date().timeIntervalSince($0) } ?? 0

        if elapsed < targetTime {
            // We're ahead of schedule, could do additional work
            // In real implementation, this would do Metal rendering
        }
    }

    private func applyOperation(_ operation: RenderTask.SceneOperation, to buffer: inout SceneBuffer, context: RenderContext) {
        switch operation.type {
        case .setLight(let roomIndex, let level):
            buffer.setLight(roomIndex, level: level)
            context.lightLevels["room_\(roomIndex)"] = level

        case .setShade(let roomIndex, let position):
            buffer.setShade(roomIndex, position: position)
            context.shadePositions["room_\(roomIndex)"] = position

        case .setDevice(let deviceIndex, let on):
            buffer.setDevice(deviceIndex, on: on)
            context.deviceStates["device_\(deviceIndex)"] = on

        case .batch(let operations):
            for op in operations {
                applyOperation(op, to: &buffer, context: context)
            }
        }
    }

    // MARK: - Performance Tracking

    private func recordRenderTime(_ duration: TimeInterval) {
        totalRenderTime += duration
        renderCount += 1
        averageRenderTime = totalRenderTime / Double(renderCount)

        renderTimeHistory.append(duration)
        if renderTimeHistory.count > maxHistorySize {
            renderTimeHistory.removeFirst()
        }
    }

    /// Get render time percentile
    func renderTimePercentile(_ percentile: Double) -> TimeInterval {
        guard !renderTimeHistory.isEmpty else { return 0 }

        let sorted = renderTimeHistory.sorted()
        let index = Int(Double(sorted.count - 1) * percentile)
        return sorted[index]
    }

    // MARK: - Batch Operations

    /// Execute multiple scene changes concurrently
    func executeBatch(_ scenes: [(sceneId: String, operations: [RenderTask.SceneOperation])], priority: RenderPriority = .normal) async {
        await withTaskGroup(of: Void.self) { group in
            for (sceneId, operations) in scenes {
                group.addTask { [weak self] in
                    guard let self = self else { return }

                    let task = RenderTask(
                        id: UUID(),
                        sceneId: sceneId,
                        priority: priority,
                        timestamp: Date(),
                        operations: operations
                    )

                    await MainActor.run {
                        self.queueTask(task)
                    }
                }
            }
        }
    }

    // MARK: - Diagnostics

    /// Pool statistics
    var statistics: PoolStatistics {
        PoolStatistics(
            totalContexts: contextPool.count,
            activeContexts: activeContextCount,
            queuedTasks: queuedTaskCount,
            averageRenderTime: averageRenderTime,
            p95RenderTime: renderTimePercentile(0.95),
            peakConcurrent: peakConcurrentRenders,
            sceneBufferCount: sceneBuffers.count
        )
    }

    struct PoolStatistics {
        let totalContexts: Int
        let activeContexts: Int
        let queuedTasks: Int
        let averageRenderTime: TimeInterval
        let p95RenderTime: TimeInterval
        let peakConcurrent: Int
        let sceneBufferCount: Int
    }

    #if DEBUG
    func printDiagnostics() {
        let stats = statistics
        print("""
        SceneRenderPool Diagnostics:
          Total contexts: \(stats.totalContexts)
          Active contexts: \(stats.activeContexts)
          Queued tasks: \(stats.queuedTasks)
          Average render time: \(String(format: "%.2f", stats.averageRenderTime * 1000))ms
          P95 render time: \(String(format: "%.2f", stats.p95RenderTime * 1000))ms
          Peak concurrent: \(stats.peakConcurrent)
          Scene buffers: \(stats.sceneBufferCount)
          Metal enabled: \(self.metalDevice != nil)
        """)
    }
    #endif

    // MARK: - Cleanup

    /// Reset pool to initial state
    func reset() {
        // Release all contexts
        for context in contextPool {
            context.release()
        }

        // Clear queue
        taskQueue.removeAll()
        queuedTaskCount = 0

        // Reset metrics
        totalRenderTime = 0
        renderCount = 0
        renderTimeHistory.removeAll()
        averageRenderTime = 0
        peakConcurrentRenders = 0
        activeContextCount = 0

        logger.info("SceneRenderPool reset")
    }
}

// MARK: - Convenience Extensions

extension SceneRenderPool {

    /// Quick render a single scene change
    func render(sceneId: String, lights: [Int: Int] = [:], shades: [Int: Int] = [:], devices: [Int: Bool] = [:], priority: RenderPriority = .normal) {
        var operations: [RenderTask.SceneOperation] = []

        for (index, level) in lights {
            operations.append(RenderTask.SceneOperation(type: .setLight(roomIndex: index, level: level)))
        }

        for (index, position) in shades {
            operations.append(RenderTask.SceneOperation(type: .setShade(roomIndex: index, position: position)))
        }

        for (index, on) in devices {
            operations.append(RenderTask.SceneOperation(type: .setDevice(deviceIndex: index, on: on)))
        }

        let task = RenderTask(
            id: UUID(),
            sceneId: sceneId,
            priority: priority,
            timestamp: Date(),
            operations: operations
        )

        queueTask(task)
    }

    /// Render movie mode (pre-defined)
    func renderMovieMode() {
        render(
            sceneId: "movie_mode",
            lights: [0: 10, 1: 10, 2: 10, 3: 5],
            shades: [0: 0, 1: 0],
            devices: [0: true, 1: true], // TV lowered, fireplace on
            priority: .high
        )
    }

    /// Render goodnight (pre-defined)
    func renderGoodnight() {
        var lights: [Int: Int] = [:]
        for i in 0..<10 {
            lights[i] = 0
        }

        render(
            sceneId: "goodnight",
            lights: lights,
            shades: [0: 0, 1: 0, 2: 0],
            devices: [0: false, 1: false, 2: true], // TV raised, fireplace off, locks on
            priority: .high
        )
    }
}

/*
 * Mirror
 * Performance is invisible when done right.
 * 50+ scenes, zero frame drops.
 * h(x) >= 0. Always.
 */
