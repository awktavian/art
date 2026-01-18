/**
 * Kagami API Service Unit Tests
 *
 * Tests for KagamiApiService network operations and state management.
 *
 * Colony: Crystal (e7) - Verification
 * h(x) >= 0. Always.
 */
package com.kagami.android.services

import android.content.SharedPreferences
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.Mockito.*
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.util.concurrent.TimeUnit

/**
 * Unit tests for KagamiApiService.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], manifest = Config.NONE)
class KagamiApiServiceTest {

    private lateinit var mockWebServer: MockWebServer
    private lateinit var apiService: KagamiApiService
    private lateinit var mockPrefs: SharedPreferences
    private lateinit var mockEditor: SharedPreferences.Editor
    private lateinit var client: OkHttpClient

    private val testDispatcher = StandardTestDispatcher()
    private val testScope = TestScope(testDispatcher)

    @Before
    fun setup() {
        mockWebServer = MockWebServer()
        mockWebServer.start()

        // Create mock SharedPreferences
        mockPrefs = mock(SharedPreferences::class.java)
        mockEditor = mock(SharedPreferences.Editor::class.java)

        `when`(mockPrefs.edit()).thenReturn(mockEditor)
        `when`(mockEditor.putString(anyString(), anyString())).thenReturn(mockEditor)
        `when`(mockEditor.putLong(anyString(), anyLong())).thenReturn(mockEditor)
        `when`(mockEditor.remove(anyString())).thenReturn(mockEditor)

        // Create OkHttpClient with short timeouts for testing
        client = OkHttpClient.Builder()
            .connectTimeout(1, TimeUnit.SECONDS)
            .readTimeout(1, TimeUnit.SECONDS)
            .build()

        apiService = KagamiApiService(client, mockPrefs)
    }

    @After
    fun tearDown() {
        mockWebServer.shutdown()
        apiService.disconnect()
    }

    // ==================== Token Management Tests ====================

    @Test
    fun `getAccessToken returns null when not stored`() {
        `when`(mockPrefs.getString("access_token", null)).thenReturn(null)

        val token = apiService.getAccessToken()

        assertNull(token)
    }

    @Test
    fun `getAccessToken returns stored token`() {
        val expectedToken = "test_access_token_123"
        `when`(mockPrefs.getString("access_token", null)).thenReturn(expectedToken)

        val token = apiService.getAccessToken()

        assertEquals(expectedToken, token)
    }

    @Test
    fun `storeAuthTokens stores all tokens`() {
        val serverUrl = "http://test.local:8001"
        val accessToken = "access_123"
        val refreshToken = "refresh_456"

        apiService.storeAuthTokens(serverUrl, accessToken, refreshToken)

        verify(mockEditor).putString("server_url", serverUrl)
        verify(mockEditor).putString("access_token", accessToken)
        verify(mockEditor).putString("refresh_token", refreshToken)
        verify(mockEditor).apply()
    }

    @Test
    fun `clearAuthTokens removes tokens`() {
        apiService.clearAuthTokens()

        verify(mockEditor).remove("access_token")
        verify(mockEditor).remove("refresh_token")
        verify(mockEditor).remove("token_stored_at")
        verify(mockEditor).apply()
    }

    @Test
    fun `isAuthenticated returns false when no token`() {
        `when`(mockPrefs.getString("access_token", null)).thenReturn(null)

        assertFalse(apiService.isAuthenticated())
    }

    @Test
    fun `isAuthenticated returns true when token exists`() {
        `when`(mockPrefs.getString("access_token", null)).thenReturn("valid_token")

        assertTrue(apiService.isAuthenticated())
    }

    @Test
    fun `isAuthenticated returns false for blank token`() {
        `when`(mockPrefs.getString("access_token", null)).thenReturn("   ")

        assertFalse(apiService.isAuthenticated())
    }

    // ==================== Connection Tests ====================

    @Test
    fun `checkConnection sets isConnected true on successful health check`() = runTest {
        val healthResponse = JSONObject().apply {
            put("status", "ok")
            put("h_x", 0.85)
        }

        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(healthResponse.toString())
        )

        // Set server URL to mock server
        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        apiService.checkConnection()

        assertTrue(apiService.isConnected.value)
        assertFalse(apiService.isOfflineMode.value)
    }

    @Test
    fun `checkConnection sets isConnected false on failed health check`() = runTest {
        mockWebServer.enqueue(MockResponse().setResponseCode(500))

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        apiService.checkConnection()

        assertFalse(apiService.isConnected.value)
        assertTrue(apiService.isOfflineMode.value)
    }

    @Test
    fun `checkConnection parses safety score from response`() = runTest {
        val expectedScore = 0.92
        val healthResponse = JSONObject().apply {
            put("status", "ok")
            put("h_x", expectedScore)
        }

        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(healthResponse.toString())
        )

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        apiService.checkConnection()

        assertEquals(expectedScore, apiService.safetyScore.value ?: 0.0, 0.001)
    }

    // ==================== Scene Execution Tests ====================

    @Test
    fun `executeScene returns success for known scene`() = runTest {
        mockWebServer.enqueue(MockResponse().setResponseCode(200))

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        val result = apiService.executeScene("movie_mode")

        assertTrue(result.isSuccess)
    }

    @Test
    fun `executeScene returns error for unknown scene`() = runTest {
        val result = apiService.executeScene("unknown_scene")

        assertTrue(result.isError)
        val error = result as com.kagami.android.data.Result.Error
        assertTrue(error.message.contains("Unknown scene"))
    }

    @Test
    fun `executeScene sends correct endpoint for movie mode`() = runTest {
        mockWebServer.enqueue(MockResponse().setResponseCode(200))

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        apiService.executeScene("movie_mode")

        val request = mockWebServer.takeRequest()
        assertEquals("/home/movie-mode/enter", request.path)
        assertEquals("POST", request.method)
    }

    @Test
    fun `executeScene sends correct endpoint for goodnight`() = runTest {
        mockWebServer.enqueue(MockResponse().setResponseCode(200))

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        apiService.executeScene("goodnight")

        val request = mockWebServer.takeRequest()
        assertEquals("/home/goodnight", request.path)
    }

    // ==================== Lights Control Tests ====================

    @Test
    fun `setLights sends correct level`() = runTest {
        mockWebServer.enqueue(MockResponse().setResponseCode(200))

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        apiService.setLights(75)

        val request = mockWebServer.takeRequest()
        assertEquals("/home/lights/set", request.path)

        val body = JSONObject(request.body.readUtf8())
        assertEquals(75, body.getInt("level"))
    }

    @Test
    fun `setLights sends room filter when specified`() = runTest {
        mockWebServer.enqueue(MockResponse().setResponseCode(200))

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        apiService.setLights(50, listOf("Living Room", "Kitchen"))

        val request = mockWebServer.takeRequest()
        val body = JSONObject(request.body.readUtf8())

        assertTrue(body.has("rooms"))
    }

    @Test
    fun `setLights returns error on network failure`() = runTest {
        mockWebServer.enqueue(MockResponse().setResponseCode(500))

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        val result = apiService.setLights(100)

        assertTrue(result.isError)
    }

    // ==================== TV Control Tests ====================

    @Test
    fun `tvControl sends correct action`() = runTest {
        mockWebServer.enqueue(MockResponse().setResponseCode(200))

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        apiService.tvControl("lower")

        val request = mockWebServer.takeRequest()
        assertEquals("/home/tv/lower", request.path)
    }

    // ==================== Shades Control Tests ====================

    @Test
    fun `controlShades sends correct action`() = runTest {
        mockWebServer.enqueue(MockResponse().setResponseCode(200))

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        apiService.controlShades("open")

        val request = mockWebServer.takeRequest()
        assertEquals("/home/shades/open", request.path)
    }

    // ==================== Fireplace Control Tests ====================

    @Test
    fun `toggleFireplace on sends correct endpoint`() = runTest {
        mockWebServer.enqueue(MockResponse().setResponseCode(200))

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        apiService.toggleFireplace(true)

        val request = mockWebServer.takeRequest()
        assertEquals("/home/fireplace/on", request.path)
    }

    @Test
    fun `toggleFireplace off sends correct endpoint`() = runTest {
        mockWebServer.enqueue(MockResponse().setResponseCode(200))

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        apiService.toggleFireplace(false)

        val request = mockWebServer.takeRequest()
        assertEquals("/home/fireplace/off", request.path)
    }

    // ==================== Rooms Fetch Tests ====================

    @Test
    fun `fetchRooms parses rooms correctly`() = runTest {
        val roomsResponse = JSONObject().apply {
            put("rooms", org.json.JSONArray().apply {
                put(JSONObject().apply {
                    put("id", "living-room")
                    put("name", "Living Room")
                    put("floor", "First Floor")
                    put("occupied", true)
                    put("lights", org.json.JSONArray().apply {
                        put(JSONObject().apply {
                            put("id", 1)
                            put("name", "Main Light")
                            put("level", 75)
                        })
                    })
                    put("shades", org.json.JSONArray().apply {
                        put(JSONObject().apply {
                            put("id", 1)
                            put("name", "Window Shade")
                            put("position", 100)
                        })
                    })
                })
            })
        }

        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(roomsResponse.toString())
        )

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        val result = apiService.fetchRooms()

        assertTrue(result.isSuccess)
        val rooms = (result as com.kagami.android.data.Result.Success).data

        assertEquals(1, rooms.size)
        assertEquals("Living Room", rooms[0].name)
        assertEquals("First Floor", rooms[0].floor)
        assertTrue(rooms[0].occupied)
        assertEquals(1, rooms[0].lights.size)
        assertEquals(75, rooms[0].lights[0].level)
    }

    @Test
    fun `fetchRooms returns empty list on empty response`() = runTest {
        val emptyResponse = JSONObject().apply {
            put("rooms", org.json.JSONArray())
        }

        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(emptyResponse.toString())
        )

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        val result = apiService.fetchRooms()

        assertTrue(result.isSuccess)
        val rooms = (result as com.kagami.android.data.Result.Success).data
        assertTrue(rooms.isEmpty())
    }

    @Test
    fun `fetchRooms returns error on network failure`() = runTest {
        mockWebServer.enqueue(MockResponse().setResponseCode(500))

        `when`(mockPrefs.getString("server_url", null))
            .thenReturn(mockWebServer.url("/").toString().trimEnd('/'))

        val result = apiService.fetchRooms()

        assertTrue(result.isError)
    }

    // ==================== State Flow Tests ====================

    @Test
    fun `initial state values are correct`() {
        assertFalse(apiService.isConnected.value)
        assertNull(apiService.safetyScore.value)
        assertEquals(0, apiService.latencyMs.value)
        assertNull(apiService.homeStatus.value)
        assertFalse(apiService.isOfflineMode.value)
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
