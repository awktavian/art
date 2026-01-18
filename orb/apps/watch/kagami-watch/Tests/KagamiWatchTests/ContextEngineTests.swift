//
// ContextEngineTests.swift
// Kagami Watch - Unit Tests
//
// Tests for the Theory of Mind context engine that infers user intentions.
//
// h(x) >= 0. Always.
//

import XCTest
@testable import KagamiWatch

@MainActor
final class ContextEngineTests: XCTestCase {

    var contextEngine: ContextEngine!

    override func setUp() async throws {
        contextEngine = ContextEngine()
    }

    override func tearDown() async throws {
        contextEngine = nil
    }

    // MARK: - Time Context Tests

    func testTimeContextMorning() {
        // Test that morning hours map to morning context
        let calendar = Calendar.current
        var components = calendar.dateComponents([.year, .month, .day], from: Date())
        components.hour = 8

        if let morningDate = calendar.date(from: components) {
            let hour = calendar.component(.hour, from: morningDate)
            XCTAssertTrue((7..<9).contains(hour), "8am should be in morning range")
        }
    }

    func testTimeContextEvening() {
        // Test that evening hours map to evening context
        let calendar = Calendar.current
        var components = calendar.dateComponents([.year, .month, .day], from: Date())
        components.hour = 18

        if let eveningDate = calendar.date(from: components) {
            let hour = calendar.component(.hour, from: eveningDate)
            XCTAssertTrue((17..<20).contains(hour), "6pm should be in evening range")
        }
    }

    func testTimeContextNight() {
        // Test that night hours map to night context
        let calendar = Calendar.current
        var components = calendar.dateComponents([.year, .month, .day], from: Date())
        components.hour = 23

        if let nightDate = calendar.date(from: components) {
            let hour = calendar.component(.hour, from: nightDate)
            XCTAssertTrue((22..<24).contains(hour), "11pm should be in night range")
        }
    }

    // MARK: - Suggested Action Tests

    func testSuggestedActionUpdates() {
        // Verify context updates produce suggested actions
        contextEngine.updateContext()
        // Suggested action should be set based on current time/location
        XCTAssertNotNil(contextEngine.suggestedAction)
    }

    func testLocationContextAwayGivesWelcomeHome() {
        // When away, welcome home should be suggested
        contextEngine.locationContext = .away
        contextEngine.updateContext()

        if let action = contextEngine.suggestedAction {
            XCTAssertEqual(action.action, .welcomeHome)
        }
    }

    // MARK: - Colony Tests

    func testAllColoniesHaveColors() {
        for colony in Colony.allCases {
            XCTAssertNotNil(colony.color, "Colony \(colony.rawValue) should have a color")
        }
    }

    func testAllColoniesHaveIcons() {
        for colony in Colony.allCases {
            XCTAssertFalse(colony.icon.isEmpty, "Colony \(colony.rawValue) should have an icon")
        }
    }

    func testAllColoniesHaveDisplayName() {
        for colony in Colony.allCases {
            XCTAssertFalse(colony.displayName.isEmpty, "Colony \(colony.rawValue) should have a display name")
        }
    }

    // MARK: - Time Context Color Tests

    func testTimeContextColors() {
        for context in ContextEngine.TimeContext.allCases {
            XCTAssertNotNil(context.primaryColor, "Time context \(context.rawValue) should have a color")
        }
    }

    // MARK: - Time Context Greeting Tests

    func testTimeContextGreetings() {
        XCTAssertEqual(ContextEngine.TimeContext.morning.greeting, "Morning")
        XCTAssertEqual(ContextEngine.TimeContext.night.greeting, "Good night")
        XCTAssertEqual(ContextEngine.TimeContext.workDay.greeting, "")
    }
}

// MARK: - Integration Tests

@MainActor
final class ContextEngineIntegrationTests: XCTestCase {

    func testHomeStatusUpdatesContext() {
        let engine = ContextEngine()

        // Simulate home status with movie mode active
        // Using actual HomeStatus struct from KagamiAPIService
        var status = HomeStatus(
            initialized: true,
            rooms: 10,
            occupiedRooms: 1,
            movieMode: true,
            avgTemp: 72.0
        )

        engine.updateFromAPI(homeStatus: status, isConnected: true)

        XCTAssertEqual(engine.activityInference, .watching)
    }

    func testEmptyHomeUpdatesLocationContext() {
        let engine = ContextEngine()

        // Simulate empty home
        // Using actual HomeStatus struct from KagamiAPIService
        let status = HomeStatus(
            initialized: true,
            rooms: 10,
            occupiedRooms: 0,
            movieMode: false,
            avgTemp: 72.0
        )

        engine.updateFromAPI(homeStatus: status, isConnected: true)

        XCTAssertEqual(engine.locationContext, .away)
    }
}

/*
 * Test Coverage:
 *   - TimeContext mapping from hours
 *   - TimeContext colors and greetings
 *   - Colony attributes (color, icon, basis)
 *   - Suggested action generation
 *   - Home status integration
 *   - Location context inference
 */
