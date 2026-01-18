//
// XCTestCase+Extensions.swift -- XCUITest Helpers for Kagami iOS
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Provides convenience methods for E2E testing:
//   - Element waiting with configurable timeouts
//   - Screenshot capture on failure
//   - Accessibility identifier helpers
//
// h(x) >= 0. Always.
//

import XCTest

extension XCTestCase {

    // MARK: - Default Timeouts

    /// Standard timeout for element appearance (5 seconds)
    static let defaultTimeout: TimeInterval = 5.0

    /// Extended timeout for slow operations (15 seconds)
    static let extendedTimeout: TimeInterval = 15.0

    /// Quick timeout for immediate checks (2 seconds)
    static let quickTimeout: TimeInterval = 2.0

    // MARK: - Element Waiting

    /// Wait for an element to exist with a custom timeout
    /// - Parameters:
    ///   - element: The XCUIElement to wait for
    ///   - timeout: Maximum time to wait (defaults to 5 seconds)
    ///   - file: Source file for failure reporting
    ///   - line: Source line for failure reporting
    /// - Returns: Whether the element exists
    @discardableResult
    func waitForElement(
        _ element: XCUIElement,
        timeout: TimeInterval = defaultTimeout,
        file: StaticString = #file,
        line: UInt = #line
    ) -> Bool {
        let exists = element.waitForExistence(timeout: timeout)
        if !exists {
            XCTFail("Element \(element) did not appear within \(timeout) seconds", file: file, line: line)
        }
        return exists
    }

    /// Wait for an element to disappear
    /// - Parameters:
    ///   - element: The XCUIElement to wait for
    ///   - timeout: Maximum time to wait
    /// - Returns: Whether the element disappeared
    @discardableResult
    func waitForElementToDisappear(
        _ element: XCUIElement,
        timeout: TimeInterval = defaultTimeout,
        file: StaticString = #file,
        line: UInt = #line
    ) -> Bool {
        let predicate = NSPredicate(format: "exists == false")
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: element)
        let result = XCTWaiter.wait(for: [expectation], timeout: timeout)

        if result != .completed {
            XCTFail("Element \(element) did not disappear within \(timeout) seconds", file: file, line: line)
            return false
        }
        return true
    }

    /// Wait for an element to be hittable (visible and interactable)
    /// - Parameters:
    ///   - element: The XCUIElement to wait for
    ///   - timeout: Maximum time to wait
    /// - Returns: Whether the element is hittable
    @discardableResult
    func waitForElementToBeHittable(
        _ element: XCUIElement,
        timeout: TimeInterval = defaultTimeout,
        file: StaticString = #file,
        line: UInt = #line
    ) -> Bool {
        let predicate = NSPredicate(format: "isHittable == true")
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: element)
        let result = XCTWaiter.wait(for: [expectation], timeout: timeout)

        if result != .completed {
            XCTFail("Element \(element) is not hittable within \(timeout) seconds", file: file, line: line)
            return false
        }
        return true
    }

    // MARK: - Screenshot Helpers

    /// Take a screenshot and attach it to the test
    /// - Parameter name: Name for the screenshot
    func takeScreenshot(named name: String) {
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    /// Take a screenshot on test failure
    func takeScreenshotOnFailure() {
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "Failure-\(Date().ISO8601Format())"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    // MARK: - Accessibility Identifier Helpers

    /// Find an element by accessibility identifier
    /// - Parameters:
    ///   - identifier: The accessibility identifier
    ///   - app: The XCUIApplication instance
    /// - Returns: The matching XCUIElement
    func element(withIdentifier identifier: String, in app: XCUIApplication) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }

    /// Check if an element with identifier exists
    /// - Parameters:
    ///   - identifier: The accessibility identifier
    ///   - app: The XCUIApplication instance
    ///   - timeout: Maximum time to wait
    /// - Returns: Whether the element exists
    @discardableResult
    func elementExists(
        withIdentifier identifier: String,
        in app: XCUIApplication,
        timeout: TimeInterval = defaultTimeout
    ) -> Bool {
        let element = app.descendants(matching: .any).matching(identifier: identifier).firstMatch
        return element.waitForExistence(timeout: timeout)
    }

    /// Tap an element by accessibility identifier
    /// - Parameters:
    ///   - identifier: The accessibility identifier
    ///   - app: The XCUIApplication instance
    ///   - timeout: Maximum time to wait for element
    func tap(
        identifier: String,
        in app: XCUIApplication,
        timeout: TimeInterval = defaultTimeout,
        file: StaticString = #file,
        line: UInt = #line
    ) {
        let element = app.descendants(matching: .any).matching(identifier: identifier).firstMatch
        guard waitForElement(element, timeout: timeout, file: file, line: line) else { return }
        element.tap()
    }

    /// Type text into a text field by accessibility identifier
    /// - Parameters:
    ///   - text: Text to type
    ///   - identifier: The accessibility identifier
    ///   - app: The XCUIApplication instance
    func typeText(
        _ text: String,
        into identifier: String,
        in app: XCUIApplication,
        timeout: TimeInterval = defaultTimeout,
        file: StaticString = #file,
        line: UInt = #line
    ) {
        let element = app.textFields[identifier].firstMatch
        guard waitForElement(element, timeout: timeout, file: file, line: line) else { return }
        element.tap()
        element.typeText(text)
    }

    /// Type text into a text field by accessibility identifier (shorthand)
    /// - Parameters:
    ///   - text: Text to type
    ///   - identifier: The accessibility identifier
    ///   - app: The XCUIApplication instance
    func typeText(
        _ text: String,
        identifier: String,
        in app: XCUIApplication,
        timeout: TimeInterval = defaultTimeout,
        file: StaticString = #file,
        line: UInt = #line
    ) {
        typeText(text, into: identifier, in: app, timeout: timeout, file: file, line: line)
    }

    /// Tap on a static text element
    /// - Parameters:
    ///   - text: The text to tap
    ///   - app: The XCUIApplication instance
    func tap(
        text: String,
        in app: XCUIApplication,
        timeout: TimeInterval = defaultTimeout,
        file: StaticString = #file,
        line: UInt = #line
    ) {
        let element = app.staticTexts[text].firstMatch
        guard waitForElement(element, timeout: timeout, file: file, line: line) else { return }
        element.tap()
    }

    /// Assert that text is NOT present on screen
    func assertTextNotPresent(
        _ text: String,
        in app: XCUIApplication,
        file: StaticString = #file,
        line: UInt = #line
    ) {
        let element = app.staticTexts[text].firstMatch
        XCTAssertFalse(
            element.exists,
            "Text '\(text)' should not be present on screen",
            file: file,
            line: line
        )
    }

    // MARK: - Swipe Helpers

    /// Swipe left on an element
    func swipeLeft(on element: XCUIElement) {
        element.swipeLeft()
    }

    /// Swipe right on an element
    func swipeRight(on element: XCUIElement) {
        element.swipeRight()
    }

    /// Swipe up on an element
    func swipeUp(on element: XCUIElement) {
        element.swipeUp()
    }

    /// Swipe down on an element
    func swipeDown(on element: XCUIElement) {
        element.swipeDown()
    }

    // MARK: - Assertion Helpers

    /// Assert that an element is visible on screen
    func assertVisible(
        _ element: XCUIElement,
        timeout: TimeInterval = defaultTimeout,
        file: StaticString = #file,
        line: UInt = #line
    ) {
        XCTAssertTrue(
            element.waitForExistence(timeout: timeout) && element.isHittable,
            "Element \(element) should be visible",
            file: file,
            line: line
        )
    }

    /// Assert that an element is not visible
    func assertNotVisible(
        _ element: XCUIElement,
        file: StaticString = #file,
        line: UInt = #line
    ) {
        XCTAssertFalse(
            element.exists && element.isHittable,
            "Element \(element) should not be visible",
            file: file,
            line: line
        )
    }

    /// Assert that text is present on screen
    func assertTextPresent(
        _ text: String,
        in app: XCUIApplication,
        timeout: TimeInterval = defaultTimeout,
        file: StaticString = #file,
        line: UInt = #line
    ) {
        let element = app.staticTexts[text].firstMatch
        XCTAssertTrue(
            element.waitForExistence(timeout: timeout),
            "Text '\(text)' should be present on screen",
            file: file,
            line: line
        )
    }
}

/*
 * Mirror
 * E2E tests ensure the full user experience works.
 * h(x) >= 0. Always.
 */
