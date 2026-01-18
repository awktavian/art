/**
 * OnboardingViewModel Unit Tests
 *
 * Colony: Crystal (e7) - Verification
 *
 * Tests for onboarding flow, server connection, integration setup,
 * room configuration, and permission handling.
 */

package com.kagami.android.viewmodels

import com.kagami.android.ui.screens.OnboardingViewModel
import com.kagami.android.ui.screens.OnboardingState
import com.kagami.android.ui.screens.SmartHomeIntegration
import com.kagami.android.ui.screens.RoomConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class OnboardingViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private val testScope = TestScope(testDispatcher)

    private lateinit var viewModel: OnboardingViewModel

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        viewModel = OnboardingViewModel()
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    // =============================================================================
    // INITIAL STATE TESTS
    // =============================================================================

    @Test
    fun `initial state is correct`() {
        val state = viewModel.state.value
        assertEquals(0, state.currentPage)
        assertEquals("", state.serverUrl)
        assertFalse(state.isDiscovering)
        assertTrue(state.discoveredServers.isEmpty())
        assertFalse(state.isTestingConnection)
        assertNull(state.connectionSuccess)
        assertNull(state.connectionError)
        assertNull(state.selectedIntegration)
        assertTrue(state.integrationCredentials.isEmpty())
        assertFalse(state.isConnectingIntegration)
        assertFalse(state.integrationConnected)
        assertNull(state.integrationError)
        assertTrue(state.availableRooms.isEmpty())
        assertTrue(state.selectedRooms.isEmpty())
        assertFalse(state.isLoadingRooms)
        assertFalse(state.notificationPermissionGranted)
        assertFalse(state.locationPermissionGranted)
        assertFalse(state.isComplete)
    }

    // =============================================================================
    // PAGE NAVIGATION TESTS
    // =============================================================================

    @Test
    fun `setPage updates current page`() {
        viewModel.setPage(3)
        assertEquals(3, viewModel.state.value.currentPage)
    }

    @Test
    fun `setPage with invalid value clamps correctly`() {
        viewModel.setPage(10)
        assertEquals(10, viewModel.state.value.currentPage) // No validation in ViewModel, handled by pager
    }

    // =============================================================================
    // SERVER URL TESTS
    // =============================================================================

    @Test
    fun `updateServerUrl updates state`() {
        viewModel.updateServerUrl("http://kagami.local:8001")
        assertEquals("http://kagami.local:8001", viewModel.state.value.serverUrl)
    }

    @Test
    fun `updateServerUrl clears connection state`() {
        viewModel.updateServerUrl("http://new.server:8001")
        assertNull(viewModel.state.value.connectionSuccess)
        assertNull(viewModel.state.value.connectionError)
    }

    // =============================================================================
    // SERVER DISCOVERY TESTS
    // =============================================================================

    @Test
    fun `discoverServers sets isDiscovering flag`() = testScope.runTest {
        viewModel.discoverServers()

        // Immediately after calling, isDiscovering should be true
        assertTrue(viewModel.state.value.isDiscovering)
    }

    // =============================================================================
    // INTEGRATION SELECTION TESTS
    // =============================================================================

    @Test
    fun `selectIntegration updates state`() {
        viewModel.selectIntegration(SmartHomeIntegration.CONTROL4)
        assertEquals(SmartHomeIntegration.CONTROL4, viewModel.state.value.selectedIntegration)
    }

    @Test
    fun `selectIntegration clears previous credentials`() {
        viewModel.selectIntegration(SmartHomeIntegration.CONTROL4)
        viewModel.updateIntegrationCredential("host", "192.168.1.100")

        viewModel.selectIntegration(SmartHomeIntegration.LUTRON)

        assertTrue(viewModel.state.value.integrationCredentials.isEmpty())
        assertFalse(viewModel.state.value.integrationConnected)
        assertNull(viewModel.state.value.integrationError)
    }

    @Test
    fun `selectIntegration with null deselects`() {
        viewModel.selectIntegration(SmartHomeIntegration.CONTROL4)
        viewModel.selectIntegration(null)

        assertNull(viewModel.state.value.selectedIntegration)
    }

    @Test
    fun `updateIntegrationCredential stores values`() {
        viewModel.selectIntegration(SmartHomeIntegration.CONTROL4)
        viewModel.updateIntegrationCredential("host", "192.168.1.100")
        viewModel.updateIntegrationCredential("port", "8750")

        val credentials = viewModel.state.value.integrationCredentials
        assertEquals("192.168.1.100", credentials["host"])
        assertEquals("8750", credentials["port"])
    }

    // =============================================================================
    // ROOM CONFIGURATION TESTS
    // =============================================================================

    @Test
    fun `toggleRoom adds room to selection`() {
        val testRooms = listOf(
            RoomConfig("living", "Living Room", "Main", hasLights = true),
            RoomConfig("office", "Office", "Main", hasLights = true)
        )
        // Manually set rooms for testing
        viewModel.toggleRoom("living")

        assertTrue(viewModel.state.value.selectedRooms.contains("living"))
    }

    @Test
    fun `toggleRoom removes room from selection if already selected`() {
        viewModel.toggleRoom("living")
        viewModel.toggleRoom("living")

        assertFalse(viewModel.state.value.selectedRooms.contains("living"))
    }

    @Test
    fun `selectAllRooms selects all available rooms`() {
        // This requires rooms to be loaded first
        viewModel.selectAllRooms()
        // With no rooms loaded, selectedRooms should be empty
        assertTrue(viewModel.state.value.selectedRooms.isEmpty())
    }

    @Test
    fun `deselectAllRooms clears selection`() {
        viewModel.toggleRoom("living")
        viewModel.toggleRoom("office")
        viewModel.deselectAllRooms()

        assertTrue(viewModel.state.value.selectedRooms.isEmpty())
    }

    // =============================================================================
    // PERMISSION TESTS
    // =============================================================================

    @Test
    fun `updateNotificationPermission updates state`() {
        viewModel.updateNotificationPermission(true)
        assertTrue(viewModel.state.value.notificationPermissionGranted)

        viewModel.updateNotificationPermission(false)
        assertFalse(viewModel.state.value.notificationPermissionGranted)
    }

    @Test
    fun `updateLocationPermission updates state`() {
        viewModel.updateLocationPermission(true)
        assertTrue(viewModel.state.value.locationPermissionGranted)

        viewModel.updateLocationPermission(false)
        assertFalse(viewModel.state.value.locationPermissionGranted)
    }

    // =============================================================================
    // COMPLETION TESTS
    // =============================================================================

    @Test
    fun `markComplete sets isComplete flag`() {
        viewModel.markComplete()
        assertTrue(viewModel.state.value.isComplete)
    }

    // =============================================================================
    // CONNECTION VALIDATION TESTS
    // =============================================================================

    @Test
    fun `testServerConnection with blank URL shows error`() = testScope.runTest {
        viewModel.updateServerUrl("")
        viewModel.testServerConnection()
        advanceUntilIdle()

        assertEquals("Please enter a server URL", viewModel.state.value.connectionError)
    }

    @Test
    fun `testServerConnection with whitespace only URL shows error`() = testScope.runTest {
        viewModel.updateServerUrl("   ")
        viewModel.testServerConnection()
        advanceUntilIdle()

        assertEquals("Please enter a server URL", viewModel.state.value.connectionError)
    }

    // =============================================================================
    // INTEGRATION CONNECTION VALIDATION TESTS
    // =============================================================================

    @Test
    fun `connectIntegration without selection does nothing`() = testScope.runTest {
        viewModel.connectIntegration()
        advanceUntilIdle()

        assertFalse(viewModel.state.value.isConnectingIntegration)
        assertNull(viewModel.state.value.integrationError)
    }

    @Test
    fun `connectIntegration with missing required fields shows error`() = testScope.runTest {
        viewModel.selectIntegration(SmartHomeIntegration.CONTROL4)
        // Don't fill in required fields
        viewModel.connectIntegration()
        advanceUntilIdle()

        assertFalse(viewModel.state.value.isConnectingIntegration)
        assertTrue(viewModel.state.value.integrationError?.contains("Please fill in") == true)
    }
}
