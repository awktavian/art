//
// LocalizationTests.swift -- Unit Tests for Localization
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Tests the LocalizationManager including:
//   - Supported languages
//   - Translation key lookups
//   - RTL detection
//   - Interpolation
//
// Run:
//   swift test --filter LocalizationTests
//
// h(x) >= 0. Always.
//

import XCTest
@testable import KagamiIOS

final class LocalizationTests: XCTestCase {

    // MARK: - Supported Languages

    func testSupportedLanguageDisplayNames() {
        XCTAssertEqual(SupportedLanguage.english.displayName, "English")
    }

    func testSupportedLanguageRawValues() {
        XCTAssertEqual(SupportedLanguage.english.rawValue, "en")
    }

    func testSupportedLanguageIsRTL() {
        // Currently only English is implemented, which is LTR
        XCTAssertFalse(SupportedLanguage.english.isRTL)
    }

    func testImplementedLanguages() {
        // Only English is currently implemented
        XCTAssertEqual(SupportedLanguage.implementedLanguages.count, 1)
        XCTAssertTrue(SupportedLanguage.implementedLanguages.contains(.english))
    }

    func testSupportedLanguageIdentifiable() {
        // Test that SupportedLanguage conforms to Identifiable
        let english = SupportedLanguage.english
        XCTAssertEqual(english.id, "en")
    }

    // MARK: - Translation Functions

    @MainActor
    func testTranslationFallback() {
        // Non-existent keys should return the key itself
        let result = t("nonexistent.key")
        XCTAssertEqual(result, "nonexistent.key")
    }

    @MainActor
    func testTranslationCommonKeys() {
        // Common keys should return actual translations
        let ok = t("common.ok")
        XCTAssertEqual(ok, "OK")

        let cancel = t("common.cancel")
        XCTAssertEqual(cancel, "Cancel")

        let save = t("common.save")
        XCTAssertEqual(save, "Save")
    }

    @MainActor
    func testTranslationHomeKeys() {
        let title = t("home.title")
        XCTAssertEqual(title, "Home")

        let welcome = t("home.welcome")
        XCTAssertEqual(welcome, "Welcome")
    }

    @MainActor
    func testTranslationDeviceKeys() {
        let lights = t("devices.lights")
        XCTAssertEqual(lights, "Lights")

        let shades = t("devices.shades")
        XCTAssertEqual(shades, "Shades")
    }

    @MainActor
    func testTranslationSceneKeys() {
        let movieMode = t("scenes.movie_mode")
        XCTAssertEqual(movieMode, "Movie Mode")

        let goodnight = t("scenes.goodnight")
        XCTAssertEqual(goodnight, "Goodnight")
    }

    @MainActor
    func testTranslationErrorKeys() {
        let generic = t("errors.generic")
        XCTAssertTrue(generic.contains("wrong"))

        let network = t("errors.network")
        XCTAssertTrue(network.contains("connect"))
    }

    // MARK: - Interpolation

    @MainActor
    func testTranslationInterpolation() {
        // Test interpolation with args
        // Note: This tests the interpolation mechanism even if the key doesn't have placeholders
        let result = t("common.ok", args: ["unused": "value"])
        XCTAssertEqual(result, "OK")
    }

    // MARK: - Pluralization

    @MainActor
    func testPluralTranslation() {
        // Test plural function (will return key.one or key.other)
        let singleResult = tp("items", count: 1)
        let pluralResult = tp("items", count: 5)

        // Since we don't have plural keys in fallback, should return formatted key
        XCTAssertTrue(singleResult.contains("items"))
        XCTAssertTrue(pluralResult.contains("items"))
    }
}

// MARK: - LocalizationManager Tests

@MainActor
final class LocalizationManagerTests: XCTestCase {

    func testSharedInstance() {
        let manager = LocalizationManager.shared
        XCTAssertNotNil(manager)
    }

    func testCurrentLanguageDefault() {
        let manager = LocalizationManager.shared
        // Should default to English (only implemented language)
        XCTAssertEqual(manager.currentLanguage, .english)
    }

    func testIsRTLForEnglish() {
        let manager = LocalizationManager.shared
        // English is not RTL
        XCTAssertFalse(manager.isRTL)
    }
}

/*
 * Mirror
 * Localization is verified programmatically.
 * h(x) >= 0. Always.
 */
