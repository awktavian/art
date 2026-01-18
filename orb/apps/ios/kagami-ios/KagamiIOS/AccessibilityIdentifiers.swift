//
// AccessibilityIdentifiers.swift -- Centralized Accessibility Identifiers for Testing
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Provides consistent, testable accessibility identifiers for:
//   - XCUITests (E2E flows)
//   - Snapshot tests
//   - VoiceOver navigation
//
// Usage:
//   .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.welcomeTitle)
//
// h(x) >= 0. Always.
//

import SwiftUI

/// Centralized accessibility identifiers for E2E testing
enum AccessibilityIdentifiers {

    // MARK: - Onboarding Flow

    enum Onboarding {
        static let progressIndicator = "onboarding.progress"
        static let skipButton = "onboarding.skip"
        static let backButton = "onboarding.back"
        static let continueButton = "onboarding.continue"
        static let getStartedButton = "onboarding.getStarted"

        // Welcome Step
        static let welcomeKanji = "onboarding.welcome.kanji"
        static let welcomeTitle = "onboarding.welcome.title"
        static let welcomeSubtitle = "onboarding.welcome.subtitle"
        static let welcomeFeatureList = "onboarding.welcome.features"
        static let skipToDemoButton = "onboarding.welcome.skipToDemo"

        // Server Step
        static let serverSearchButton = "onboarding.server.search"
        static let serverList = "onboarding.server.list"
        static let serverURLField = "onboarding.server.urlField"
        static let serverDemoButton = "onboarding.server.demo"
        static let serverConnectionStatus = "onboarding.server.status"

        // Integration Step
        static let integrationGrid = "onboarding.integration.grid"
        static let integrationCredentialsSheet = "onboarding.integration.credentials"
        static let integrationTestButton = "onboarding.integration.test"
        static let integrationStatus = "onboarding.integration.status"

        // Rooms Step
        static let roomsList = "onboarding.rooms.list"
        static let roomsSelectAll = "onboarding.rooms.selectAll"
        static let roomsRefresh = "onboarding.rooms.refresh"

        // Permissions Step
        static let permissionsList = "onboarding.permissions.list"
        static let permissionsEnableAll = "onboarding.permissions.enableAll"

        // Completion Step
        static let completionCheckmark = "onboarding.completion.checkmark"
        static let completionTitle = "onboarding.completion.title"
        static let completionTips = "onboarding.completion.tips"

        /// Generate identifier for a specific step
        static func step(_ step: Int) -> String {
            "onboarding.step.\(step)"
        }

        /// Generate identifier for integration card
        static func integrationCard(_ id: String) -> String {
            "onboarding.integration.card.\(id)"
        }

        /// Generate identifier for room toggle
        static func roomToggle(_ roomId: String) -> String {
            "onboarding.rooms.toggle.\(roomId)"
        }

        /// Generate identifier for permission row
        static func permissionRow(_ permissionId: String) -> String {
            "onboarding.permissions.row.\(permissionId)"
        }
    }

    // MARK: - Home View

    enum Home {
        static let view = "home.view"
        static let kanji = "home.kanji"
        static let title = "home.title"
        static let safetyCard = "home.safetyCard"
        static let safetyScore = "home.safetyScore"
        static let heroAction = "home.heroAction"
        static let quickActions = "home.quickActions"
        static let fireplaceStatus = "home.fireplaceStatus"
        static let connectionIndicator = "home.connectionIndicator"
    }

    // MARK: - Rooms View

    enum Rooms {
        static let view = "rooms.view"
        static let list = "rooms.list"
        static let refreshButton = "rooms.refresh"
        static let emptyState = "rooms.emptyState"
        static let loadingIndicator = "rooms.loading"
        static let errorMessage = "rooms.error"
        static let retryButton = "rooms.retry"

        /// Generate identifier for a room row
        static func row(_ roomId: String) -> String {
            "rooms.row.\(roomId)"
        }

        /// Generate identifier for room light button
        static func lightButton(_ roomId: String, level: String) -> String {
            "rooms.row.\(roomId).light.\(level)"
        }

        /// Generate identifier for room brightness bar
        static func brightnessBar(_ roomId: String) -> String {
            "rooms.row.\(roomId).brightness"
        }
    }

    // MARK: - Scenes View

    enum Scenes {
        static let view = "scenes.view"
        static let list = "scenes.list"

        /// Generate identifier for a scene row
        static func row(_ sceneId: String) -> String {
            "scenes.row.\(sceneId)"
        }

        /// Generate identifier for scene activate button
        static func activateButton(_ sceneId: String) -> String {
            "scenes.row.\(sceneId).activate"
        }
    }

    // MARK: - Quick Actions

    enum QuickActions {
        static let section = "quickActions.section"
        static let lightsOn = "quickActions.lightsOn"
        static let lightsOff = "quickActions.lightsOff"
        static let fireplace = "quickActions.fireplace"
        static let tvLower = "quickActions.tvLower"
        static let tvRaise = "quickActions.tvRaise"
        static let shadesOpen = "quickActions.shadesOpen"
    }

    // MARK: - Settings View

    enum Settings {
        static let view = "settings.view"
        static let serverSection = "settings.server"
        static let accountSection = "settings.account"
        static let aboutSection = "settings.about"
        static let logoutButton = "settings.logout"
        static let versionLabel = "settings.version"
    }

    // MARK: - Hub View

    enum Hub {
        static let view = "hub.view"
        static let statusIndicator = "hub.status"
        static let connectionInfo = "hub.connectionInfo"
    }

    // MARK: - Voice Command View

    enum VoiceCommand {
        static let view = "voiceCommand.view"
        static let micButton = "voiceCommand.mic"
        static let transcriptLabel = "voiceCommand.transcript"
        static let statusIndicator = "voiceCommand.status"
    }

    // MARK: - Composer Bar

    enum Composer {
        static let bar = "composer.bar"
        static let textField = "composer.textField"
        static let sendButton = "composer.send"
        static let voiceButton = "composer.voice"
    }

    // MARK: - Tab Bar

    enum TabBar {
        static let home = "tabBar.home"
        static let rooms = "tabBar.rooms"
        static let hub = "tabBar.hub"
        static let scenes = "tabBar.scenes"
        static let settings = "tabBar.settings"
    }

    // MARK: - Common Components

    enum Common {
        static let loadingSpinner = "common.loading"
        static let errorAlert = "common.errorAlert"
        static let successToast = "common.successToast"
        static let dismissButton = "common.dismiss"
        static let cancelButton = "common.cancel"
        static let confirmButton = "common.confirm"
    }
}

// MARK: - View Extension for Easy Application

extension View {
    /// Apply accessibility identifier from AccessibilityIdentifiers enum
    func testIdentifier(_ identifier: String) -> some View {
        self.accessibilityIdentifier(identifier)
    }
}

/*
 * Mirror
 * Every element must be testable.
 * Accessibility serves both humans and machines.
 * h(x) >= 0. Always.
 */
