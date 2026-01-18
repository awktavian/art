//
// CommandParserTests.swift
// Kagami Watch - Unit Tests for Command Parser
//
// Tests for voice command intent detection and pattern matching.
//
// h(x) >= 0. Always.
//

import XCTest
@testable import KagamiWatch

// MARK: - Command Parser Tests

final class CommandParserTests: XCTestCase {

    // MARK: - Scene Intent Tests

    func testMovieModeSceneDetection() {
        XCTAssertEqual(CommandParser.parse("movie mode"), .scene(.movieMode))
        XCTAssertEqual(CommandParser.parse("Let's watch a movie"), .scene(.movieMode))
        XCTAssertEqual(CommandParser.parse("Start movie mode"), .scene(.movieMode))
        XCTAssertEqual(CommandParser.parse("Film time"), .scene(.movieMode))
        XCTAssertEqual(CommandParser.parse("watch something"), .scene(.movieMode))
        XCTAssertEqual(CommandParser.parse("watch tv"), .scene(.movieMode))
    }

    func testGoodnightSceneDetection() {
        XCTAssertEqual(CommandParser.parse("goodnight"), .scene(.goodnight))
        XCTAssertEqual(CommandParser.parse("good night"), .scene(.goodnight))
        XCTAssertEqual(CommandParser.parse("bed time"), .scene(.goodnight))
        XCTAssertEqual(CommandParser.parse("going to bed"), .scene(.goodnight))
        XCTAssertEqual(CommandParser.parse("I'm going to sleep"), .scene(.goodnight))
    }

    func testWelcomeHomeSceneDetection() {
        XCTAssertEqual(CommandParser.parse("welcome home"), .scene(.welcomeHome))
        XCTAssertEqual(CommandParser.parse("I'm home"), .scene(.welcomeHome))
        XCTAssertEqual(CommandParser.parse("arrived home"), .scene(.welcomeHome))
        XCTAssertEqual(CommandParser.parse("home mode"), .scene(.welcomeHome))
    }

    func testAwaySceneDetection() {
        XCTAssertEqual(CommandParser.parse("away mode"), .scene(.away))
        XCTAssertEqual(CommandParser.parse("leaving home"), .scene(.away))
        XCTAssertEqual(CommandParser.parse("goodbye"), .scene(.away))
        XCTAssertEqual(CommandParser.parse("I'm leaving now"), .scene(.away))
    }

    func testFocusSceneDetection() {
        XCTAssertEqual(CommandParser.parse("focus mode"), .scene(.focusMode))
        XCTAssertEqual(CommandParser.parse("work mode"), .scene(.focusMode))
        XCTAssertEqual(CommandParser.parse("I need to concentrate"), .scene(.focusMode))
    }

    // MARK: - Scene False Positive Tests

    func testWatchAloneDoesNotTriggerMovieMode() {
        // "watch" alone without context shouldn't trigger movie mode
        let result = CommandParser.parse("watch the house")
        XCTAssertNotEqual(result, .scene(.movieMode))
    }

    func testHomeAloneDoesNotTriggerWelcomeHome() {
        // "home" alone is too ambiguous
        let result = CommandParser.parse("home")
        XCTAssertNotEqual(result, .scene(.welcomeHome))
    }

    func testByeAloneDoesNotTriggerAway() {
        // "bye" alone is too weak
        let result = CommandParser.parse("bye")
        XCTAssertNotEqual(result, .scene(.away))
    }

    // MARK: - Lights Intent Tests

    func testLightsOn() {
        XCTAssertEqual(CommandParser.parse("turn on the lights"), .lights(.on))
        XCTAssertEqual(CommandParser.parse("lights on"), .lights(.on))
    }

    func testLightsOff() {
        XCTAssertEqual(CommandParser.parse("turn off the lights"), .lights(.off))
        XCTAssertEqual(CommandParser.parse("lights off"), .lights(.off))
        XCTAssertEqual(CommandParser.parse("lights dark"), .lights(.off))
    }

    func testLightsDim() {
        XCTAssertEqual(CommandParser.parse("dim the lights"), .lights(.dim))
        XCTAssertEqual(CommandParser.parse("lights low"), .lights(.dim))
    }

    func testLightsBright() {
        XCTAssertEqual(CommandParser.parse("bright lights"), .lights(.bright))
        XCTAssertEqual(CommandParser.parse("lights full"), .lights(.bright))
        XCTAssertEqual(CommandParser.parse("max lights"), .lights(.bright))
    }

    func testLightsPercentage() {
        XCTAssertEqual(CommandParser.parse("lights to 50"), .lights(.setLevel(50)))
        XCTAssertEqual(CommandParser.parse("lights 50%"), .lights(.setLevel(50)))
        XCTAssertEqual(CommandParser.parse("set lights to 75 percent"), .lights(.setLevel(75)))
        XCTAssertEqual(CommandParser.parse("lights at 30"), .lights(.setLevel(30)))
    }

    func testLightsPercentageClamping() {
        // Should clamp to 0-100
        XCTAssertEqual(CommandParser.parse("lights to 150"), .lights(.setLevel(100)))
    }

    func testLightsToggle() {
        // "lights" alone should toggle
        XCTAssertEqual(CommandParser.parse("lights"), .lights(.toggle))
    }

    // MARK: - Fireplace Intent Tests

    func testFireplaceOn() {
        XCTAssertEqual(CommandParser.parse("turn on the fireplace"), .fireplace(.on))
        XCTAssertEqual(CommandParser.parse("start fire"), .fireplace(.on))
        XCTAssertEqual(CommandParser.parse("light the fire"), .fireplace(.on))
    }

    func testFireplaceOff() {
        XCTAssertEqual(CommandParser.parse("turn off the fireplace"), .fireplace(.off))
        XCTAssertEqual(CommandParser.parse("stop fire"), .fireplace(.off))
        XCTAssertEqual(CommandParser.parse("extinguish fireplace"), .fireplace(.off))
    }

    func testFireplaceToggle() {
        XCTAssertEqual(CommandParser.parse("fireplace"), .fireplace(.toggle))
        XCTAssertEqual(CommandParser.parse("fire"), .fireplace(.toggle))
    }

    // MARK: - TV Intent Tests

    func testTVRaise() {
        XCTAssertEqual(CommandParser.parse("raise the tv"), .tv(.raise))
        XCTAssertEqual(CommandParser.parse("tv up"), .tv(.raise))
        XCTAssertEqual(CommandParser.parse("hide the screen"), .tv(.raise))
    }

    func testTVLower() {
        XCTAssertEqual(CommandParser.parse("lower the tv"), .tv(.lower))
        XCTAssertEqual(CommandParser.parse("tv down"), .tv(.lower))
        XCTAssertEqual(CommandParser.parse("show the tv"), .tv(.lower))
    }

    func testTVToggle() {
        XCTAssertEqual(CommandParser.parse("tv"), .tv(.toggle))
    }

    // MARK: - Shades Intent Tests

    func testShadesOpen() {
        XCTAssertEqual(CommandParser.parse("open the shades"), .shades(.open))
        XCTAssertEqual(CommandParser.parse("blinds up"), .shades(.open))
        XCTAssertEqual(CommandParser.parse("raise the curtains"), .shades(.open))
    }

    func testShadesClose() {
        XCTAssertEqual(CommandParser.parse("close the shades"), .shades(.close))
        XCTAssertEqual(CommandParser.parse("blinds down"), .shades(.close))
        XCTAssertEqual(CommandParser.parse("shut the curtains"), .shades(.close))
    }

    func testShadesToggle() {
        XCTAssertEqual(CommandParser.parse("shades"), .shades(.toggle))
        XCTAssertEqual(CommandParser.parse("blinds"), .shades(.toggle))
    }

    // MARK: - Unknown Intent Tests

    func testUnknownCommand() {
        XCTAssertEqual(CommandParser.parse("random gibberish xyz"), .unknown)
        XCTAssertEqual(CommandParser.parse("what's the weather"), .unknown)
        XCTAssertEqual(CommandParser.parse("hello there"), .unknown)
    }

    // MARK: - Punctuation and Case Handling

    func testIgnoresPunctuation() {
        XCTAssertEqual(CommandParser.parse("Turn on the lights!"), .lights(.on))
        XCTAssertEqual(CommandParser.parse("Movie mode?"), .scene(.movieMode))
        XCTAssertEqual(CommandParser.parse("Goodnight..."), .scene(.goodnight))
    }

    func testCaseInsensitive() {
        XCTAssertEqual(CommandParser.parse("LIGHTS ON"), .lights(.on))
        XCTAssertEqual(CommandParser.parse("Movie Mode"), .scene(.movieMode))
        XCTAssertEqual(CommandParser.parse("GOODNIGHT"), .scene(.goodnight))
    }

    // MARK: - Debug Output Tests

    func testDebugParseOutput() {
        XCTAssertEqual(CommandParser.debugParse("movie mode"), "Scene: Movie Mode")
        XCTAssertEqual(CommandParser.debugParse("lights 50"), "Lights: 50%")
        XCTAssertEqual(CommandParser.debugParse("unknown command"), "Unknown command")
    }
}
