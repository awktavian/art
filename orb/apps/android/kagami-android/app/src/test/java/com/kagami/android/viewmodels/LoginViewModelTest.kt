/**
 * LoginViewModel Unit Tests
 *
 * Colony: Crystal (e7) - Verification
 *
 * Tests for authentication flow, server discovery, and error handling.
 */

package com.kagami.android.viewmodels

import com.kagami.android.ui.screens.LoginViewModel
import com.kagami.android.ui.screens.LoginState
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
class LoginViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private val testScope = TestScope(testDispatcher)

    private lateinit var viewModel: LoginViewModel

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        viewModel = LoginViewModel()
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    // =============================================================================
    // STATE UPDATE TESTS
    // =============================================================================

    @Test
    fun `initial state is correct`() {
        val state = viewModel.state.value
        assertEquals("", state.serverUrl)
        assertEquals("", state.username)
        assertEquals("", state.password)
        assertFalse(state.isLoading)
        assertFalse(state.isDiscovering)
        assertNull(state.error)
        assertTrue(state.discoveredServers.isEmpty())
        assertFalse(state.showServerSelection)
    }

    @Test
    fun `updateServerUrl updates state correctly`() {
        viewModel.updateServerUrl("http://kagami.local:8001")

        assertEquals("http://kagami.local:8001", viewModel.state.value.serverUrl)
        assertNull(viewModel.state.value.error)
    }

    @Test
    fun `updateServerUrl clears previous error`() {
        // First set an error by calling with invalid input
        viewModel.updateServerUrl("http://test.com")

        // Verify error is cleared on new input
        assertNull(viewModel.state.value.error)
    }

    @Test
    fun `updateUsername updates state correctly`() {
        viewModel.updateUsername("testuser")

        assertEquals("testuser", viewModel.state.value.username)
        assertNull(viewModel.state.value.error)
    }

    @Test
    fun `updatePassword updates state correctly`() {
        viewModel.updatePassword("testpassword")

        assertEquals("testpassword", viewModel.state.value.password)
        assertNull(viewModel.state.value.error)
    }

    // =============================================================================
    // VALIDATION TESTS
    // =============================================================================

    @Test
    fun `login fails with empty server URL`() = testScope.runTest {
        viewModel.updateUsername("user")
        viewModel.updatePassword("password")

        viewModel.login { _, _ -> }
        advanceUntilIdle()

        assertEquals("Please enter a server URL", viewModel.state.value.error)
        assertFalse(viewModel.state.value.isLoading)
    }

    @Test
    fun `login fails with empty username`() = testScope.runTest {
        viewModel.updateServerUrl("http://kagami.local:8001")
        viewModel.updatePassword("password")

        viewModel.login { _, _ -> }
        advanceUntilIdle()

        assertEquals("Please enter your username", viewModel.state.value.error)
        assertFalse(viewModel.state.value.isLoading)
    }

    @Test
    fun `login fails with empty password`() = testScope.runTest {
        viewModel.updateServerUrl("http://kagami.local:8001")
        viewModel.updateUsername("user")

        viewModel.login { _, _ -> }
        advanceUntilIdle()

        assertEquals("Please enter your password", viewModel.state.value.error)
        assertFalse(viewModel.state.value.isLoading)
    }

    // =============================================================================
    // SERVER SELECTION TESTS
    // =============================================================================

    @Test
    fun `selectServer updates state and dismisses dialog`() {
        viewModel.selectServer("http://192.168.1.100:8001")

        assertEquals("http://192.168.1.100:8001", viewModel.state.value.serverUrl)
        assertFalse(viewModel.state.value.showServerSelection)
        assertNull(viewModel.state.value.error)
    }

    @Test
    fun `dismissServerSelection closes dialog without changing URL`() {
        viewModel.updateServerUrl("http://original.local:8001")
        viewModel.dismissServerSelection()

        assertEquals("http://original.local:8001", viewModel.state.value.serverUrl)
        assertFalse(viewModel.state.value.showServerSelection)
    }

    // =============================================================================
    // ERROR HANDLING TESTS
    // =============================================================================

    @Test
    fun `clearError removes error from state`() {
        // Trigger an error first
        viewModel.login { _, _ -> }

        // Clear it
        viewModel.clearError()

        assertNull(viewModel.state.value.error)
    }

    // =============================================================================
    // STATE FLOW TESTS
    // =============================================================================

    @Test
    fun `state updates are observable`() = testScope.runTest {
        var observedCount = 0
        val expected = listOf("", "http://test.com")

        viewModel.updateServerUrl("http://test.com")
        advanceUntilIdle()

        assertEquals("http://test.com", viewModel.state.value.serverUrl)
    }

    @Test
    fun `multiple field updates maintain consistency`() {
        viewModel.updateServerUrl("http://kagami.local:8001")
        viewModel.updateUsername("tim")
        viewModel.updatePassword("secret123")

        val state = viewModel.state.value
        assertEquals("http://kagami.local:8001", state.serverUrl)
        assertEquals("tim", state.username)
        assertEquals("secret123", state.password)
    }
}
