//
// OfflinePersistenceServiceTests.swift
// Kagami Watch - Unit Tests for Offline Persistence Service
//
// Tests for queue operations, file persistence, and offline mode.
//
// h(x) >= 0. Always.
//

import XCTest
@testable import KagamiWatch

// MARK: - Offline Persistence Service Tests

@MainActor
final class OfflinePersistenceServiceTests: XCTestCase {

    var persistenceService: OfflinePersistenceService!

    override func setUp() async throws {
        persistenceService = OfflinePersistenceService.shared
        // Clear state for clean tests
        persistenceService.clearAllData()
    }

    override func tearDown() async throws {
        persistenceService.clearAllData()
        persistenceService = nil
    }

    // MARK: - Initial State Tests

    func testInitialStateHasDefaultScenes() {
        // After initialization, should have default scenes
        XCTAssertFalse(persistenceService.cachedScenes.isEmpty)
        XCTAssertTrue(persistenceService.cachedScenes.count >= 5) // goodnight, movie_mode, welcome_home, away, focus
    }

    func testDefaultScenesIncludeExpected() {
        let sceneIds = persistenceService.cachedScenes.map { $0.id }

        XCTAssertTrue(sceneIds.contains("goodnight"), "Should have goodnight scene")
        XCTAssertTrue(sceneIds.contains("movie_mode"), "Should have movie_mode scene")
        XCTAssertTrue(sceneIds.contains("welcome_home"), "Should have welcome_home scene")
        XCTAssertTrue(sceneIds.contains("away"), "Should have away scene")
        XCTAssertTrue(sceneIds.contains("focus"), "Should have focus scene")
    }

    func testInitialStateNotOffline() {
        XCTAssertFalse(persistenceService.isOfflineMode)
    }

    func testInitialStateNoPendingActions() {
        XCTAssertTrue(persistenceService.pendingActions.isEmpty)
    }

    // MARK: - Offline Mode Tests

    func testEnterOfflineMode() {
        XCTAssertFalse(persistenceService.isOfflineMode)

        persistenceService.enterOfflineMode()

        XCTAssertTrue(persistenceService.isOfflineMode)
    }

    func testExitOfflineMode() {
        persistenceService.enterOfflineMode()
        XCTAssertTrue(persistenceService.isOfflineMode)

        persistenceService.exitOfflineMode()

        XCTAssertFalse(persistenceService.isOfflineMode)
    }

    func testOfflineModePersistedToUserDefaults() {
        persistenceService.enterOfflineMode()

        let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
        let storedValue = defaults?.bool(forKey: "isOfflineMode")

        XCTAssertTrue(storedValue == true)
    }

    // MARK: - Home State Caching Tests

    func testUpdateHomeStateLightLevel() {
        XCTAssertNil(persistenceService.cachedHomeState)

        persistenceService.updateHomeState(lightLevel: 75)

        XCTAssertNotNil(persistenceService.cachedHomeState)
        XCTAssertEqual(persistenceService.cachedHomeState?.lightLevel, 75)
    }

    func testUpdateHomeStateMovieMode() {
        persistenceService.updateHomeState(movieMode: true)

        XCTAssertTrue(persistenceService.cachedHomeState?.movieMode == true)
    }

    func testUpdateHomeStateFireplace() {
        persistenceService.updateHomeState(fireplaceOn: true)

        XCTAssertTrue(persistenceService.cachedHomeState?.fireplaceOn == true)
    }

    func testUpdateHomeStateMultipleProperties() {
        persistenceService.updateHomeState(
            lightLevel: 50,
            movieMode: true,
            fireplaceOn: true,
            occupiedRooms: 3,
            temperature: 72.5
        )

        let state = persistenceService.cachedHomeState
        XCTAssertEqual(state?.lightLevel, 50)
        XCTAssertTrue(state?.movieMode == true)
        XCTAssertTrue(state?.fireplaceOn == true)
        XCTAssertEqual(state?.occupiedRooms, 3)
        XCTAssertEqual(state?.temperature, 72.5)
    }

    func testUpdateHomeStateTimestamp() {
        let beforeUpdate = Date()
        persistenceService.updateHomeState(lightLevel: 100)
        let afterUpdate = Date()

        let timestamp = persistenceService.cachedHomeState?.lastUpdated
        XCTAssertNotNil(timestamp)
        XCTAssertTrue(timestamp! >= beforeUpdate && timestamp! <= afterUpdate)
    }

    func testCacheUpdateSetsLastCacheUpdate() {
        XCTAssertNil(persistenceService.lastCacheUpdate)

        persistenceService.updateHomeState(lightLevel: 25)

        XCTAssertNotNil(persistenceService.lastCacheUpdate)
    }

    func testHomeStateStaleAfter30Minutes() {
        // Create a state with old timestamp
        var oldState = OfflinePersistenceService.CachedHomeState(
            lightLevel: 50,
            movieMode: false,
            fireplaceOn: false,
            occupiedRooms: 1,
            temperature: 70.0,
            lastUpdated: Date().addingTimeInterval(-1900) // 31+ minutes ago
        )

        XCTAssertTrue(oldState.isStale)
    }

    func testHomeStateNotStaleWhenRecent() {
        let recentState = OfflinePersistenceService.CachedHomeState(
            lightLevel: 50,
            movieMode: false,
            fireplaceOn: false,
            occupiedRooms: 1,
            temperature: 70.0,
            lastUpdated: Date() // Now
        )

        XCTAssertFalse(recentState.isStale)
    }

    // MARK: - Pending Actions Queue Tests

    func testQueueAction() {
        XCTAssertTrue(persistenceService.pendingActions.isEmpty)

        persistenceService.queueAction(
            actionType: "POST",
            endpoint: "/home/lights/set",
            body: ["level": 80]
        )

        XCTAssertEqual(persistenceService.pendingActions.count, 1)
    }

    func testQueuedActionHasCorrectProperties() {
        persistenceService.queueAction(
            actionType: "POST",
            endpoint: "/home/scenes/movie_mode/execute"
        )

        let action = persistenceService.pendingActions.first
        XCTAssertEqual(action?.actionType, "POST")
        XCTAssertEqual(action?.endpoint, "/home/scenes/movie_mode/execute")
        XCTAssertEqual(action?.retryCount, 0)
    }

    func testQueuedActionHasUniqueId() {
        persistenceService.queueAction(actionType: "POST", endpoint: "/test1")
        persistenceService.queueAction(actionType: "POST", endpoint: "/test2")

        let ids = persistenceService.pendingActions.map { $0.id }
        XCTAssertEqual(Set(ids).count, 2) // All IDs should be unique
    }

    func testQueuedActionHasTimestamp() {
        let beforeQueue = Date()
        persistenceService.queueAction(actionType: "POST", endpoint: "/test")
        let afterQueue = Date()

        let action = persistenceService.pendingActions.first
        XCTAssertNotNil(action?.createdAt)
        XCTAssertTrue(action!.createdAt >= beforeQueue && action!.createdAt <= afterQueue)
    }

    func testRemoveAction() {
        persistenceService.queueAction(actionType: "POST", endpoint: "/test1")
        persistenceService.queueAction(actionType: "POST", endpoint: "/test2")

        XCTAssertEqual(persistenceService.pendingActions.count, 2)

        let actionToRemove = persistenceService.pendingActions.first!
        persistenceService.removeAction(actionToRemove)

        XCTAssertEqual(persistenceService.pendingActions.count, 1)
        XCTAssertFalse(persistenceService.pendingActions.contains { $0.id == actionToRemove.id })
    }

    func testGetNextPendingAction() {
        persistenceService.queueAction(actionType: "POST", endpoint: "/first")
        persistenceService.queueAction(actionType: "POST", endpoint: "/second")

        let next = persistenceService.getNextPendingAction()

        // Should return oldest first
        XCTAssertEqual(next?.endpoint, "/first")
    }

    func testGetNextPendingActionSkipsExceededRetries() {
        persistenceService.queueAction(actionType: "POST", endpoint: "/failed")

        // Increment retry count beyond limit
        let actionId = persistenceService.pendingActions.first!.id
        for _ in 0..<6 {
            persistenceService.incrementRetryCount(for: actionId)
        }

        let next = persistenceService.getNextPendingAction()

        // Should not return action with too many retries
        XCTAssertNil(next)
    }

    func testIncrementRetryCount() {
        persistenceService.queueAction(actionType: "POST", endpoint: "/test")

        let actionId = persistenceService.pendingActions.first!.id
        XCTAssertEqual(persistenceService.pendingActions.first?.retryCount, 0)

        persistenceService.incrementRetryCount(for: actionId)
        XCTAssertEqual(persistenceService.pendingActions.first?.retryCount, 1)

        persistenceService.incrementRetryCount(for: actionId)
        XCTAssertEqual(persistenceService.pendingActions.first?.retryCount, 2)
    }

    func testClearPendingActions() {
        persistenceService.queueAction(actionType: "POST", endpoint: "/test1")
        persistenceService.queueAction(actionType: "POST", endpoint: "/test2")
        persistenceService.queueAction(actionType: "POST", endpoint: "/test3")

        XCTAssertEqual(persistenceService.pendingActions.count, 3)

        persistenceService.clearPendingActions()

        XCTAssertTrue(persistenceService.pendingActions.isEmpty)
    }

    // MARK: - Scene Caching Tests

    func testGetCachedScene() {
        let scene = persistenceService.getCachedScene(id: "goodnight")

        XCTAssertNotNil(scene)
        XCTAssertEqual(scene?.name, "Goodnight")
        XCTAssertEqual(scene?.icon, "moon.fill")
    }

    func testGetCachedSceneNotFound() {
        let scene = persistenceService.getCachedScene(id: "nonexistent")

        XCTAssertNil(scene)
    }

    func testMarkSceneUsedUpdatesStats() {
        let initialUsageCount = persistenceService.getCachedScene(id: "movie_mode")?.usageCount ?? 0

        persistenceService.markSceneUsed(id: "movie_mode")

        let updatedUsageCount = persistenceService.getCachedScene(id: "movie_mode")?.usageCount ?? 0
        XCTAssertEqual(updatedUsageCount, initialUsageCount + 1)
    }

    func testMarkSceneUsedSetsLastUsed() {
        let scene = persistenceService.getCachedScene(id: "goodnight")
        XCTAssertNil(scene?.lastUsed)

        let beforeMark = Date()
        persistenceService.markSceneUsed(id: "goodnight")
        let afterMark = Date()

        let updatedScene = persistenceService.getCachedScene(id: "goodnight")
        XCTAssertNotNil(updatedScene?.lastUsed)
        XCTAssertTrue(updatedScene!.lastUsed! >= beforeMark && updatedScene!.lastUsed! <= afterMark)
    }

    // MARK: - Scene Action Types Tests

    func testSceneActionsTypes() {
        let goodnightScene = persistenceService.getCachedScene(id: "goodnight")

        XCTAssertNotNil(goodnightScene?.actions)
        XCTAssertFalse(goodnightScene!.actions.isEmpty)

        // Goodnight should have setLights, controlShades, fireplace actions
        let actionTypes = goodnightScene!.actions.map { $0.type }
        XCTAssertTrue(actionTypes.contains(.setLights))
        XCTAssertTrue(actionTypes.contains(.controlShades))
        XCTAssertTrue(actionTypes.contains(.fireplace))
    }

    func testMovieModeSceneActions() {
        let movieScene = persistenceService.getCachedScene(id: "movie_mode")

        let actionTypes = movieScene!.actions.map { $0.type }
        XCTAssertTrue(actionTypes.contains(.setLights))
        XCTAssertTrue(actionTypes.contains(.controlShades))
        XCTAssertTrue(actionTypes.contains(.tvControl))
    }

    // MARK: - Clear All Data Tests

    func testClearAllData() {
        // Set up some state
        persistenceService.updateHomeState(lightLevel: 50)
        persistenceService.queueAction(actionType: "POST", endpoint: "/test")

        // Clear everything
        persistenceService.clearAllData()

        // Home state should be nil
        XCTAssertNil(persistenceService.cachedHomeState)

        // Pending actions should be empty
        XCTAssertTrue(persistenceService.pendingActions.isEmpty)

        // Last cache update should be nil
        XCTAssertNil(persistenceService.lastCacheUpdate)

        // Default scenes should be restored
        XCTAssertFalse(persistenceService.cachedScenes.isEmpty)
    }

    // MARK: - Body Serialization Tests

    func testQueueActionSerializesBody() {
        let body: [String: Any] = [
            "level": 75,
            "rooms": ["Living Room", "Kitchen"]
        ]

        persistenceService.queueAction(
            actionType: "POST",
            endpoint: "/home/lights/set",
            body: body
        )

        let action = persistenceService.pendingActions.first
        XCTAssertNotNil(action?.body)

        // Verify body is valid JSON
        if let bodyData = action?.body,
           let decoded = try? JSONSerialization.jsonObject(with: bodyData) as? [String: Any] {
            XCTAssertEqual(decoded["level"] as? Int, 75)
            XCTAssertEqual(decoded["rooms"] as? [String], ["Living Room", "Kitchen"])
        } else {
            XCTFail("Body should be valid JSON")
        }
    }

    func testQueueActionWithNilBody() {
        persistenceService.queueAction(
            actionType: "POST",
            endpoint: "/home/fireplace/toggle"
        )

        let action = persistenceService.pendingActions.first
        XCTAssertNil(action?.body)
    }

    // MARK: - UserDefaults Integration Tests

    func testHomeStateUpdatesSharedContainer() {
        persistenceService.updateHomeState(
            lightLevel: 65,
            movieMode: true,
            fireplaceOn: true
        )

        let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
        XCTAssertEqual(defaults?.integer(forKey: "cachedLightLevel"), 65)
        XCTAssertTrue(defaults?.bool(forKey: "cachedMovieMode") == true)
        XCTAssertTrue(defaults?.bool(forKey: "cachedFireplaceOn") == true)
        XCTAssertNotNil(defaults?.object(forKey: "lastCacheUpdate"))
    }
}
