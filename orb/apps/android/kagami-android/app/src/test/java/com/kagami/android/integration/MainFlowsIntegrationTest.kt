/**
 * Kagami Android Integration Tests
 *
 * Integration tests for main user flows across screens.
 * Tests the complete user journey from login through scene activation.
 *
 * Colony: Crystal (e7) - Verification
 * h(x) >= 0. Always.
 */
package com.kagami.android.integration

import android.content.SharedPreferences
import com.kagami.android.data.Result
import com.kagami.android.services.KagamiApiService
import com.kagami.android.services.Light
import com.kagami.android.services.RoomModel
import com.kagami.android.services.Shade
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.json.JSONArray
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
 * Integration tests for main application flows.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], manifest = Config.NONE)
class MainFlowsIntegrationTest {

    private lateinit var mockWebServer: MockWebServer
    private lateinit var apiService: KagamiApiService
    private lateinit var mockPrefs: SharedPreferences
    private lateinit var mockEditor: SharedPreferences.Editor
    private lateinit var client: OkHttpClient

    // Stored token for authentication tests
    private var storedAccessToken: String? = null
    private var storedServerUrl: String? = null

    @Before
    fun setup() {
        mockWebServer = MockWebServer()
        mockWebServer.start()

        // Create mock SharedPreferences with state tracking
        mockPrefs = mock(SharedPreferences::class.java)
        mockEditor = mock(SharedPreferences.Editor::class.java)

        `when`(mockPrefs.edit()).thenReturn(mockEditor)
        `when`(mockEditor.putString(anyString(), anyString())).thenAnswer { invocation ->
            val key = invocation.arguments[0] as String
            val value = invocation.arguments[1] as String
            when (key) {
                "access_token" -> storedAccessToken = value
                "server_url" -> storedServerUrl = value
            }
            mockEditor
        }
        `when`(mockEditor.putLong(anyString(), anyLong())).thenReturn(mockEditor)
        `when`(mockEditor.remove(anyString())).thenReturn(mockEditor)

        `when`(mockPrefs.getString(eq("access_token"), isNull())).thenAnswer {
            storedAccessToken
        }
        `when`(mockPrefs.getString(eq("server_url"), isNull())).thenAnswer {
            storedServerUrl ?: mockWebServer.url("/").toString().trimEnd('/')
        }

        client = OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(5, TimeUnit.SECONDS)
            .build()

        apiService = KagamiApiService(client, mockPrefs)
    }

    @After
    fun tearDown() {
        mockWebServer.shutdown()
        apiService.disconnect()
        storedAccessToken = null
        storedServerUrl = null
    }

    // ==================== Complete User Flow Tests ====================

    /**
     * Test the complete flow: Connect -> Check Health -> Fetch Rooms -> Control Lights
     */
    @Test
    fun `complete home control flow works end to end`() = runTest {
        // Setup dispatcher to handle multiple requests
        mockWebServer.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                return when (request.path) {
                    "/health" -> MockResponse()
                        .setResponseCode(200)
                        .setBody(createHealthResponse())

                    "/home/rooms" -> MockResponse()
                        .setResponseCode(200)
                        .setBody(createRoomsResponse())

                    "/home/lights/set" -> MockResponse()
                        .setResponseCode(200)
                        .setBody("{\"success\": true}")

                    else -> MockResponse().setResponseCode(404)
                }
            }
        }

        // Step 1: Check connection
        apiService.checkConnection()
        assertTrue("Should be connected", apiService.isConnected.value)
        assertNotNull("Should have safety score", apiService.safetyScore.value)

        // Step 2: Fetch rooms
        val roomsResult = apiService.fetchRooms()
        assertTrue("Rooms fetch should succeed", roomsResult.isSuccess)

        val rooms = (roomsResult as Result.Success).data
        assertEquals("Should have 2 rooms", 2, rooms.size)

        // Step 3: Control lights in a room
        val livingRoom = rooms.find { it.name == "Living Room" }
        assertNotNull("Should find Living Room", livingRoom)

        val lightsResult = apiService.setLights(100, listOf(livingRoom!!.id))
        assertTrue("Lights control should succeed", lightsResult.isSuccess)
    }

    /**
     * Test scene activation flow with all common scenes.
     */
    @Test
    fun `scene activation flow works for all scenes`() = runTest {
        val activatedScenes = mutableListOf<String>()

        mockWebServer.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                // Track which scene endpoints are called
                val path = request.path ?: ""
                when {
                    path.contains("movie-mode") -> activatedScenes.add("movie_mode")
                    path.contains("goodnight") -> activatedScenes.add("goodnight")
                    path.contains("welcome-home") -> activatedScenes.add("welcome_home")
                    path.contains("away") -> activatedScenes.add("away")
                    path.contains("fireplace") -> activatedScenes.add("fireplace")
                }
                return MockResponse().setResponseCode(200).setBody("{\"success\": true}")
            }
        }

        // Test each common scene
        val scenesToTest = listOf("movie_mode", "goodnight", "welcome_home", "away", "relax")

        for (scene in scenesToTest) {
            val result = apiService.executeScene(scene)
            assertTrue("Scene $scene should succeed", result.isSuccess)
        }

        // Verify scenes were activated
        assertTrue("Movie mode should be activated", "movie_mode" in activatedScenes)
        assertTrue("Goodnight should be activated", "goodnight" in activatedScenes)
        assertTrue("Welcome home should be activated", "welcome_home" in activatedScenes)
        assertTrue("Away should be activated", "away" in activatedScenes)
        assertTrue("Fireplace (relax) should be activated", "fireplace" in activatedScenes)
    }

    /**
     * Test authentication flow including token storage and usage.
     */
    @Test
    fun `authentication flow stores and uses tokens correctly`() = runTest {
        val testToken = "test_access_token_abc123"
        val testRefreshToken = "test_refresh_token_xyz789"
        val serverUrl = mockWebServer.url("/").toString().trimEnd('/')

        // Step 1: Store auth tokens (simulating successful login)
        apiService.storeAuthTokens(serverUrl, testToken, testRefreshToken)

        // Verify storage was called
        verify(mockEditor).putString("access_token", testToken)
        verify(mockEditor).putString("refresh_token", testRefreshToken)
        verify(mockEditor).putString("server_url", serverUrl)

        // Step 2: Verify token is used in subsequent requests
        var authHeaderReceived: String? = null

        mockWebServer.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                authHeaderReceived = request.getHeader("Authorization")
                return MockResponse()
                    .setResponseCode(200)
                    .setBody(createRoomsResponse())
            }
        }

        // Update mock to return the stored token
        storedAccessToken = testToken

        apiService.fetchRooms()

        assertEquals(
            "Authorization header should contain token",
            "Bearer $testToken",
            authHeaderReceived
        )
    }

    /**
     * Test offline mode behavior when connection fails.
     */
    @Test
    fun `offline mode activates when connection fails`() = runTest {
        // Configure server to fail
        mockWebServer.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                return MockResponse().setResponseCode(503)
            }
        }

        // Check connection should fail
        apiService.checkConnection()

        assertFalse("Should not be connected", apiService.isConnected.value)
        assertTrue("Should be in offline mode", apiService.isOfflineMode.value)
    }

    /**
     * Test room control operations sequence.
     */
    @Test
    fun `room control sequence works correctly`() = runTest {
        val operations = mutableListOf<Pair<String, Int>>()

        mockWebServer.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path ?: ""
                if (path.contains("lights/set")) {
                    val body = JSONObject(request.body.readUtf8())
                    operations.add("lights" to body.getInt("level"))
                } else if (path.contains("shades")) {
                    val action = path.substringAfterLast("/")
                    operations.add("shades" to if (action == "open") 100 else 0)
                }
                return MockResponse().setResponseCode(200).setBody("{\"success\": true}")
            }
        }

        // Simulate typical room control sequence
        // 1. Turn lights on
        apiService.setLights(100, listOf("living-room"))
        // 2. Open shades
        apiService.controlShades("open", listOf("living-room"))
        // 3. Dim lights for movie
        apiService.setLights(30, listOf("living-room"))
        // 4. Close shades
        apiService.controlShades("close", listOf("living-room"))

        assertEquals("Should have 4 operations", 4, operations.size)
        assertEquals("First operation: lights on", "lights" to 100, operations[0])
        assertEquals("Second operation: shades open", "shades" to 100, operations[1])
        assertEquals("Third operation: lights dim", "lights" to 30, operations[2])
        assertEquals("Fourth operation: shades close", "shades" to 0, operations[3])
    }

    /**
     * Test TV control operations.
     */
    @Test
    fun `tv control operations work correctly`() = runTest {
        val tvActions = mutableListOf<String>()

        mockWebServer.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path ?: ""
                if (path.contains("/home/tv/")) {
                    tvActions.add(path.substringAfterLast("/"))
                }
                return MockResponse().setResponseCode(200).setBody("{\"success\": true}")
            }
        }

        // Lower TV
        val lowerResult = apiService.tvControl("lower")
        assertTrue("TV lower should succeed", lowerResult.isSuccess)

        // Raise TV
        val raiseResult = apiService.tvControl("raise")
        assertTrue("TV raise should succeed", raiseResult.isSuccess)

        assertEquals("Should have 2 TV actions", 2, tvActions.size)
        assertEquals("First action should be lower", "lower", tvActions[0])
        assertEquals("Second action should be raise", "raise", tvActions[1])
    }

    /**
     * Test error handling across different failure modes.
     */
    @Test
    fun `error handling works across failure modes`() = runTest {
        var requestCount = 0

        mockWebServer.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                requestCount++
                return when (requestCount) {
                    1 -> MockResponse().setResponseCode(401) // Unauthorized
                    2 -> MockResponse().setResponseCode(500) // Server error
                    3 -> MockResponse().setResponseCode(503) // Service unavailable
                    else -> MockResponse().setResponseCode(200)
                }
            }
        }

        // Each call should return an error Result, not crash
        val result1 = apiService.fetchRooms()
        assertTrue("401 should return error", result1.isError)

        val result2 = apiService.setLights(100)
        assertTrue("500 should return error", result2.isError)

        val result3 = apiService.executeScene("movie_mode")
        assertTrue("503 should return error", result3.isError)
    }

    // ==================== Helper Methods ====================

    private fun createHealthResponse(): String {
        return JSONObject().apply {
            put("status", "ok")
            put("h_x", 0.85)
            put("version", "1.0.0")
        }.toString()
    }

    private fun createRoomsResponse(): String {
        return JSONObject().apply {
            put("rooms", JSONArray().apply {
                put(JSONObject().apply {
                    put("id", "living-room")
                    put("name", "Living Room")
                    put("floor", "First Floor")
                    put("occupied", true)
                    put("lights", JSONArray().apply {
                        put(JSONObject().apply {
                            put("id", 1)
                            put("name", "Main Light")
                            put("level", 75)
                        })
                        put(JSONObject().apply {
                            put("id", 2)
                            put("name", "Accent Light")
                            put("level", 50)
                        })
                    })
                    put("shades", JSONArray().apply {
                        put(JSONObject().apply {
                            put("id", 1)
                            put("name", "Main Shade")
                            put("position", 100)
                        })
                    })
                })
                put(JSONObject().apply {
                    put("id", "bedroom")
                    put("name", "Primary Bedroom")
                    put("floor", "Second Floor")
                    put("occupied", false)
                    put("lights", JSONArray().apply {
                        put(JSONObject().apply {
                            put("id", 3)
                            put("name", "Bedroom Light")
                            put("level", 0)
                        })
                    })
                    put("shades", JSONArray())
                })
            })
        }.toString()
    }
}

/**
 * Login Flow Integration Tests
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], manifest = Config.NONE)
class LoginFlowIntegrationTest {

    private lateinit var mockWebServer: MockWebServer

    @Before
    fun setup() {
        mockWebServer = MockWebServer()
        mockWebServer.start()
    }

    @After
    fun tearDown() {
        mockWebServer.shutdown()
    }

    @Test
    fun `login flow with valid credentials succeeds`() = runTest {
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(JSONObject().apply {
                    put("access_token", "valid_token_123")
                    put("refresh_token", "refresh_token_456")
                    put("expires_in", 3600)
                }.toString())
        )

        val client = OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .build()

        val request = okhttp3.Request.Builder()
            .url(mockWebServer.url("/api/user/token"))
            .post(JSONObject().apply {
                put("username", "testuser")
                put("password", "testpass")
            }.toString().toRequestBody("application/json".toMediaType()))
            .build()

        val response = client.newCall(request).execute()

        assertTrue("Login should succeed", response.isSuccessful)

        val responseBody = JSONObject(response.body?.string() ?: "{}")
        assertEquals("valid_token_123", responseBody.getString("access_token"))
    }

    @Test
    fun `login flow with invalid credentials fails`() = runTest {
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(401)
                .setBody(JSONObject().apply {
                    put("detail", "Invalid username or password")
                }.toString())
        )

        val client = OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .build()

        val request = okhttp3.Request.Builder()
            .url(mockWebServer.url("/api/user/token"))
            .post(JSONObject().apply {
                put("username", "wronguser")
                put("password", "wrongpass")
            }.toString().toRequestBody("application/json".toMediaType()))
            .build()

        val response = client.newCall(request).execute()

        assertFalse("Login should fail", response.isSuccessful)
        assertEquals(401, response.code)
    }

    private fun String.toRequestBody(contentType: String): okhttp3.RequestBody {
        return this.toByteArray().toRequestBody(contentType.toMediaType())
    }

    private fun String.toMediaType(): okhttp3.MediaType {
        return okhttp3.MediaType.parse(this)!!
    }

    private fun ByteArray.toRequestBody(contentType: okhttp3.MediaType): okhttp3.RequestBody {
        return okhttp3.RequestBody.create(contentType, this)
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
