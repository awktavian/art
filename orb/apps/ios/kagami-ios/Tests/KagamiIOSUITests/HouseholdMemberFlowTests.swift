//
// HouseholdMemberFlowTests.swift -- E2E Tests for Household Member Management
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Tests the household member management experience across diverse personas:
//   - Solo senior (Ingrid persona)
//   - Multigenerational family (Patel persona)
//   - LGBTQ+ parents (Jordan & Sam persona)
//   - Roommate household (Tokyo persona)
//   - Single parent (Maria persona)
//   - Accessibility-focused (Michael persona)
//
// These tests validate:
//   - Member creation and editing
//   - Role and authority management
//   - Accessibility profile configuration
//   - Cultural preferences
//   - Privacy settings per household type
//
// Run:
//   xcodebuild test -scheme KagamiIOS -destination 'platform=iOS Simulator,name=iPhone 15 Pro' \
//     -only-testing:KagamiIOSUITests/HouseholdMemberFlowTests
//
// h(x) >= 0. Always.
//

import XCTest

final class HouseholdMemberFlowTests: KagamiUITestCase {

    // MARK: - Member Creation Tests

    func testCreateNewMember() {
        // Navigate to household settings
        navigateToHouseholdSettings()

        // Tap add member
        tap(identifier: AccessibilityIDs.Household.addMemberButton, in: app)

        // Verify member creation form appears
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Household.memberNameField, in: app)
        )

        // Fill in member details
        typeText("Alex", identifier: AccessibilityIDs.Household.memberNameField, in: app)

        // Select role
        tap(identifier: AccessibilityIDs.Household.roleSelector, in: app)
        tap(text: "Member", in: app)

        // Save
        tap(identifier: AccessibilityIDs.Household.saveButton, in: app)

        // Verify member appears in list
        sleep(1)
        assertTextPresent("Alex", in: app)

        takeScreenshot(named: "Household-MemberCreated")
    }

    func testCreateMemberWithPronouns() {
        navigateToHouseholdSettings()
        tap(identifier: AccessibilityIDs.Household.addMemberButton, in: app)

        // Fill basic info
        typeText("Jordan", identifier: AccessibilityIDs.Household.memberNameField, in: app)

        // Expand pronouns section
        tap(identifier: AccessibilityIDs.Household.pronounsSection, in: app)

        // Select they/them
        tap(text: "they/them", in: app)

        // Verify pronouns are selected
        assertTextPresent("they", in: app)

        takeScreenshot(named: "Household-MemberPronouns")
    }

    // MARK: - Role and Authority Tests

    func testSetMemberAsAdmin() {
        navigateToHouseholdSettings()
        createBasicMember(name: "Admin User")

        // Tap on member to edit
        tap(text: "Admin User", in: app)

        // Change role to admin
        tap(identifier: AccessibilityIDs.Household.roleSelector, in: app)
        tap(text: "Admin", in: app)

        // Verify admin badge appears
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Household.adminBadge, in: app)
        )

        // Save
        tap(identifier: AccessibilityIDs.Household.saveButton, in: app)

        takeScreenshot(named: "Household-AdminRole")
    }

    func testSetMemberAsChild() {
        navigateToHouseholdSettings()
        createBasicMember(name: "Little One")

        // Edit member
        tap(text: "Little One", in: app)

        // Change role to child
        tap(identifier: AccessibilityIDs.Household.roleSelector, in: app)
        tap(text: "Child", in: app)

        // Verify child-specific options appear
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Household.parentalControlsToggle, in: app)
        )

        takeScreenshot(named: "Household-ChildRole")
    }

    func testLimitedAuthorityMember() {
        navigateToHouseholdSettings()
        createBasicMember(name: "Guest User")

        // Edit member
        tap(text: "Guest User", in: app)

        // Set authority to limited
        tap(identifier: AccessibilityIDs.Household.authoritySelector, in: app)
        tap(text: "Limited", in: app)

        // Verify limited permissions
        assertTextPresent("Cannot control devices", in: app)
        assertTextPresent("Cannot modify scenes", in: app)

        takeScreenshot(named: "Household-LimitedAuthority")
    }

    // MARK: - Accessibility Profile Tests

    func testConfigureLowVisionProfile() {
        navigateToHouseholdSettings()
        createBasicMember(name: "Michael")

        // Edit member
        tap(text: "Michael", in: app)

        // Open accessibility section
        tap(identifier: AccessibilityIDs.Household.accessibilitySection, in: app)

        // Set vision level to low vision
        tap(identifier: AccessibilityIDs.Household.visionLevelSelector, in: app)
        tap(text: "Low Vision", in: app)

        // Verify large text recommendation appears
        assertTextPresent("Large text recommended", in: app)

        // Save
        tap(identifier: AccessibilityIDs.Household.saveButton, in: app)

        takeScreenshot(named: "Household-LowVisionProfile")
    }

    func testConfigureBlindProfile() {
        navigateToHouseholdSettings()
        createBasicMember(name: "Screen Reader User")

        // Edit member
        tap(text: "Screen Reader User", in: app)

        // Open accessibility section
        tap(identifier: AccessibilityIDs.Household.accessibilitySection, in: app)

        // Set vision level to blind
        tap(identifier: AccessibilityIDs.Household.visionLevelSelector, in: app)
        tap(text: "Blind", in: app)

        // Verify VoiceOver optimizations appear
        assertTextPresent("VoiceOver optimized", in: app)

        takeScreenshot(named: "Household-BlindProfile")
    }

    func testConfigureMotorAccessibility() {
        navigateToHouseholdSettings()
        createBasicMember(name: "Motor User")

        // Edit member
        tap(text: "Motor User", in: app)

        // Open accessibility section
        tap(identifier: AccessibilityIDs.Household.accessibilitySection, in: app)

        // Set motor control to limited
        tap(identifier: AccessibilityIDs.Household.motorControlSelector, in: app)
        tap(text: "Limited", in: app)

        // Verify large touch targets recommendation
        assertTextPresent("Large touch targets", in: app)

        takeScreenshot(named: "Household-MotorAccessibility")
    }

    func testConfigureCognitiveAccessibility() {
        navigateToHouseholdSettings()
        createBasicMember(name: "Simplified UI User")

        // Edit member
        tap(text: "Simplified UI User", in: app)

        // Open accessibility section
        tap(identifier: AccessibilityIDs.Household.accessibilitySection, in: app)

        // Set cognitive needs to simplified
        tap(identifier: AccessibilityIDs.Household.cognitiveNeedsSelector, in: app)
        tap(text: "Simplified", in: app)

        // Verify simplified mode enabled
        assertTextPresent("Simplified interface", in: app)

        takeScreenshot(named: "Household-CognitiveAccessibility")
    }

    // MARK: - Cultural Preferences Tests

    func testSetPrimaryLanguage() {
        navigateToHouseholdSettings()
        createBasicMember(name: "Spanish Speaker")

        // Edit member
        tap(text: "Spanish Speaker", in: app)

        // Open cultural preferences
        tap(identifier: AccessibilityIDs.Household.culturalSection, in: app)

        // Set primary language
        tap(identifier: AccessibilityIDs.Household.languageSelector, in: app)
        tap(text: "Spanish", in: app)

        // Verify language set
        assertTextPresent("es", in: app)

        takeScreenshot(named: "Household-SpanishLanguage")
    }

    func testSetPrivacyOrientation() {
        navigateToHouseholdSettings()
        createBasicMember(name: "Privacy User")

        // Edit member
        tap(text: "Privacy User", in: app)

        // Open cultural preferences
        tap(identifier: AccessibilityIDs.Household.culturalSection, in: app)

        // Set privacy orientation to individualist
        tap(identifier: AccessibilityIDs.Household.privacyOrientationSelector, in: app)
        tap(text: "Individualist", in: app)

        // Verify privacy boundaries explained
        assertTextPresent("Personal data not shared", in: app)

        takeScreenshot(named: "Household-IndividualistPrivacy")
    }

    func testSetCollectivistPrivacy() {
        navigateToHouseholdSettings()
        createBasicMember(name: "Family Member")

        // Edit member
        tap(text: "Family Member", in: app)

        // Open cultural preferences
        tap(identifier: AccessibilityIDs.Household.culturalSection, in: app)

        // Set privacy orientation to collectivist
        tap(identifier: AccessibilityIDs.Household.privacyOrientationSelector, in: app)
        tap(text: "Collectivist", in: app)

        // Verify family sharing explained
        assertTextPresent("Shared with family", in: app)

        takeScreenshot(named: "Household-CollectivistPrivacy")
    }

    // MARK: - Household Type Tests

    func testSetHouseholdTypeSoloSenior() {
        navigateToHouseholdSettings()

        // Tap household type selector
        tap(identifier: AccessibilityIDs.Household.householdTypeSelector, in: app)

        // Select solo senior
        tap(text: "Solo Senior", in: app)

        // Verify accessibility defaults applied
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Household.accessibilityDefaultsApplied, in: app)
        )

        assertTextPresent("Large text enabled", in: app)
        assertTextPresent("Emergency features prioritized", in: app)

        takeScreenshot(named: "Household-SoloSeniorType")
    }

    func testSetHouseholdTypeRoommates() {
        navigateToHouseholdSettings()

        // Tap household type selector
        tap(identifier: AccessibilityIDs.Household.householdTypeSelector, in: app)

        // Select roommates
        tap(text: "Roommates", in: app)

        // Verify privacy defaults applied
        assertTextPresent("Individual privacy zones", in: app)
        assertTextPresent("Shared spaces only", in: app)

        takeScreenshot(named: "Household-RoommatesType")
    }

    func testSetHouseholdTypeMultigenerational() {
        navigateToHouseholdSettings()

        // Tap household type selector
        tap(identifier: AccessibilityIDs.Household.householdTypeSelector, in: app)

        // Select multigenerational
        tap(text: "Multigenerational", in: app)

        // Verify family features enabled
        assertTextPresent("Family calendar", in: app)
        assertTextPresent("Elder care features", in: app)
        assertTextPresent("Child safety", in: app)

        takeScreenshot(named: "Household-MultigenerationalType")
    }

    func testSetHouseholdTypeLGBTQParents() {
        navigateToHouseholdSettings()

        // Tap household type selector
        tap(identifier: AccessibilityIDs.Household.householdTypeSelector, in: app)

        // Select LGBTQ+ parents
        tap(text: "LGBTQ+ Parents", in: app)

        // Verify inclusive features
        assertTextPresent("Inclusive terminology", in: app)
        assertTextPresent("Custom family roles", in: app)

        takeScreenshot(named: "Household-LGBTQParentsType")
    }

    // MARK: - Member List Tests

    func testMemberListShowsAllMembers() {
        navigateToHouseholdSettings()

        // Create multiple members
        createBasicMember(name: "Member One")
        createBasicMember(name: "Member Two")
        createBasicMember(name: "Member Three")

        // Verify all members visible
        assertTextPresent("Member One", in: app)
        assertTextPresent("Member Two", in: app)
        assertTextPresent("Member Three", in: app)

        takeScreenshot(named: "Household-MemberList")
    }

    func testDeleteMember() {
        navigateToHouseholdSettings()
        createBasicMember(name: "To Be Deleted")

        // Swipe to delete
        let memberCell = app.cells.containing(.staticText, identifier: "To Be Deleted").firstMatch
        memberCell.swipeLeft()

        // Tap delete
        tap(text: "Delete", in: app)

        // Confirm deletion
        tap(text: "Confirm", in: app)

        // Verify member removed
        sleep(1)
        assertTextNotPresent("To Be Deleted", in: app)

        takeScreenshot(named: "Household-MemberDeleted")
    }

    // MARK: - Emergency Contact Tests

    func testSetEmergencyContact() {
        navigateToHouseholdSettings()
        createBasicMember(name: "Emergency Contact")

        // Edit member
        tap(text: "Emergency Contact", in: app)

        // Open emergency section
        tap(identifier: AccessibilityIDs.Household.emergencySection, in: app)

        // Mark as emergency contact
        tap(identifier: AccessibilityIDs.Household.isEmergencyContactToggle, in: app)

        // Verify emergency badge
        assertTextPresent("Emergency Contact", in: app)

        // Save
        tap(identifier: AccessibilityIDs.Household.saveButton, in: app)

        takeScreenshot(named: "Household-EmergencyContact")
    }

    // MARK: - Helper Methods

    private func navigateToHouseholdSettings() {
        // Navigate from home to settings
        tap(identifier: AccessibilityIDs.TabBar.settings, in: app)
        waitForElement(element(withIdentifier: AccessibilityIDs.Settings.view, in: app))

        // Tap household section
        tap(identifier: AccessibilityIDs.Settings.householdSection, in: app)
        waitForElement(element(withIdentifier: AccessibilityIDs.Household.view, in: app))
    }

    private func createBasicMember(name: String) {
        tap(identifier: AccessibilityIDs.Household.addMemberButton, in: app)
        waitForElement(element(withIdentifier: AccessibilityIDs.Household.memberNameField, in: app))
        typeText(name, identifier: AccessibilityIDs.Household.memberNameField, in: app)
        tap(identifier: AccessibilityIDs.Household.saveButton, in: app)
        sleep(1)
    }
}

/*
 * Mirror
 * Every household member is respected programmatically.
 * h(x) >= 0. For EVERYONE.
 */
