/**
 * Kagami Login Screen - Authentication UI for Android
 *
 * Features:
 * - Server URL field with discovery button
 * - Username and password fields
 * - Login button calling /api/user/token
 * - Create Account button
 * - Material 3 components
 *
 * Accessibility (Phase 2):
 * - TalkBack content descriptions for all interactive elements
 * - Minimum 48dp touch targets
 * - High contrast mode support
 * - Font scaling support (200%)
 */

package com.kagami.android.ui.screens

import android.view.HapticFeedbackConstants
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import com.kagami.android.R
import androidx.lifecycle.viewModelScope
import com.kagami.android.ui.MinTouchTargetSize
import com.kagami.android.ui.minTouchTarget
import com.kagami.android.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

// =============================================================================
// LOGIN STATE
// =============================================================================

data class LoginState(
    val serverUrl: String = "",
    val username: String = "",
    val password: String = "",
    val isLoading: Boolean = false,
    val isDiscovering: Boolean = false,
    val error: String? = null,
    val discoveredServers: List<String> = emptyList(),
    val showServerSelection: Boolean = false
)

// =============================================================================
// LOGIN VIEW MODEL
// =============================================================================

class LoginViewModel : ViewModel() {

    private val _state = MutableStateFlow(LoginState())
    val state: StateFlow<LoginState> = _state.asStateFlow()

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    companion object {
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()
        private val DEFAULT_SERVERS = listOf(
            "http://kagami.local:8001",
            "http://192.168.1.100:8001",
            "http://192.168.1.50:8001",
            "http://10.0.0.100:8001",
            "http://localhost:8001"
        )
    }

    fun updateServerUrl(url: String) {
        _state.value = _state.value.copy(serverUrl = url, error = null)
    }

    fun updateUsername(username: String) {
        _state.value = _state.value.copy(username = username, error = null)
    }

    fun updatePassword(password: String) {
        _state.value = _state.value.copy(password = password, error = null)
    }

    fun selectServer(url: String) {
        _state.value = _state.value.copy(
            serverUrl = url,
            showServerSelection = false,
            error = null
        )
    }

    fun dismissServerSelection() {
        _state.value = _state.value.copy(showServerSelection = false)
    }

    fun discoverServers() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isDiscovering = true, error = null)

            val discovered = mutableListOf<String>()

            withContext(Dispatchers.IO) {
                for (candidate in DEFAULT_SERVERS) {
                    if (testConnection(candidate)) {
                        discovered.add(candidate)
                    }
                }
            }

            _state.value = _state.value.copy(
                isDiscovering = false,
                discoveredServers = discovered,
                showServerSelection = discovered.isNotEmpty(),
                error = if (discovered.isEmpty()) "No Kagami servers found on your network" else null
            )

            // Auto-select if only one server found
            if (discovered.size == 1) {
                _state.value = _state.value.copy(
                    serverUrl = discovered.first(),
                    showServerSelection = false
                )
            }
        }
    }

    private fun testConnection(url: String): Boolean {
        return try {
            val request = Request.Builder().url("$url/health").build()
            val response = client.newCall(request).execute()
            response.isSuccessful
        } catch (e: Exception) {
            false
        }
    }

    fun login(onSuccess: (accessToken: String, refreshToken: String?) -> Unit) {
        val currentState = _state.value

        // Validation
        if (currentState.serverUrl.isBlank()) {
            _state.value = currentState.copy(error = "Please enter a server URL")
            return
        }
        if (currentState.username.isBlank()) {
            _state.value = currentState.copy(error = "Please enter your username")
            return
        }
        if (currentState.password.isBlank()) {
            _state.value = currentState.copy(error = "Please enter your password")
            return
        }

        viewModelScope.launch {
            _state.value = currentState.copy(isLoading = true, error = null)

            try {
                val result = withContext(Dispatchers.IO) {
                    performLogin(
                        serverUrl = currentState.serverUrl.trimEnd('/'),
                        username = currentState.username,
                        password = currentState.password
                    )
                }

                when (result) {
                    is LoginResult.Success -> {
                        _state.value = _state.value.copy(isLoading = false, error = null)
                        onSuccess(result.accessToken, result.refreshToken)
                    }
                    is LoginResult.Error -> {
                        _state.value = _state.value.copy(
                            isLoading = false,
                            error = result.message
                        )
                    }
                }
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    isLoading = false,
                    error = "Connection failed: ${e.message ?: "Unknown error"}"
                )
            }
        }
    }

    private fun performLogin(
        serverUrl: String,
        username: String,
        password: String
    ): LoginResult {
        val body = JSONObject().apply {
            put("username", username)
            put("password", password)
            put("grant_type", "password")
        }

        val request = Request.Builder()
            .url("$serverUrl/api/user/token")
            .post(body.toString().toRequestBody(JSON_MEDIA_TYPE))
            .build()

        return try {
            val response = client.newCall(request).execute()
            val responseBody = response.body?.string()

            if (response.isSuccessful && responseBody != null) {
                val json = JSONObject(responseBody)
                LoginResult.Success(
                    accessToken = json.getString("access_token"),
                    refreshToken = json.optString("refresh_token", null),
                    expiresIn = json.optInt("expires_in", 3600)
                )
            } else {
                val errorJson = responseBody?.let {
                    try { JSONObject(it) } catch (e: Exception) { null }
                }
                val errorDetail = errorJson?.optString("detail") ?: "Authentication failed"
                LoginResult.Error(errorDetail)
            }
        } catch (e: Exception) {
            LoginResult.Error("Network error: ${e.message ?: "Unable to connect"}")
        }
    }

    fun clearError() {
        _state.value = _state.value.copy(error = null)
    }
}

sealed class LoginResult {
    data class Success(
        val accessToken: String,
        val refreshToken: String?,
        val expiresIn: Int
    ) : LoginResult()

    data class Error(val message: String) : LoginResult()
}

// =============================================================================
// LOGIN SCREEN COMPOSABLE
// =============================================================================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LoginScreen(
    onLoginSuccess: (accessToken: String, refreshToken: String?) -> Unit,
    onCreateAccount: () -> Unit,
    viewModel: LoginViewModelDI
) {
    val state by viewModel.state.collectAsState()
    val view = LocalView.current
    val focusManager = LocalFocusManager.current
    val scrollState = rememberScrollState()

    var passwordVisible by remember { mutableStateOf(false) }

    // Server selection dialog
    if (state.showServerSelection && state.discoveredServers.isNotEmpty()) {
        ServerSelectionDialog(
            servers = state.discoveredServers,
            onSelect = { viewModel.selectServer(it) },
            onDismiss = { viewModel.dismissServerSelection() }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Void)
            .verticalScroll(scrollState)
            .padding(24.dp)
            .semantics(mergeDescendants = false) { },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Spacer(modifier = Modifier.weight(0.5f))

        // Logo / Title
        Icon(
            imageVector = Icons.Default.AutoAwesome,
            contentDescription = null,
            tint = Crystal.copy(alpha = 0.8f),
            modifier = Modifier
                .size(64.dp)
                .clearAndSetSemantics { }
        )

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "Kagami",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold,
            color = Color.White,
            modifier = Modifier.semantics { heading() }
        )

        Text(
            text = "Sign in to your home",
            style = MaterialTheme.typography.bodyMedium,
            color = Color.White.copy(alpha = 0.6f),
            modifier = Modifier.clearAndSetSemantics { }
        )

        Spacer(modifier = Modifier.height(48.dp))

        // Server URL Field
        OutlinedTextField(
            value = state.serverUrl,
            onValueChange = viewModel::updateServerUrl,
            label = { Text("Server URL") },
            placeholder = { Text("http://kagami.local:8001") },
            singleLine = true,
            leadingIcon = {
                Icon(
                    Icons.Default.Cloud,
                    contentDescription = null,
                    tint = Color.White.copy(alpha = 0.6f)
                )
            },
            trailingIcon = {
                IconButton(
                    onClick = {
                        view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                        viewModel.discoverServers()
                    },
                    enabled = !state.isDiscovering,
                    modifier = Modifier
                        .minTouchTarget()
                        .semantics {
                            contentDescription = "Discover Kagami servers on your network"
                            role = Role.Button
                        }
                ) {
                    if (state.isDiscovering) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            color = Crystal,
                            strokeWidth = 2.dp
                        )
                    } else {
                        Icon(
                            Icons.Default.Search,
                            contentDescription = null,
                            tint = Crystal
                        )
                    }
                }
            },
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Uri,
                imeAction = ImeAction.Next
            ),
            keyboardActions = KeyboardActions(
                onNext = { focusManager.moveFocus(FocusDirection.Down) }
            ),
            colors = kagamiTextFieldColors(),
            modifier = Modifier
                .fillMaxWidth()
                .semantics {
                    contentDescription = "Server URL. Enter the address of your Kagami server."
                }
        )

        Spacer(modifier = Modifier.height(16.dp))

        // Username Field
        OutlinedTextField(
            value = state.username,
            onValueChange = viewModel::updateUsername,
            label = { Text("Username") },
            singleLine = true,
            leadingIcon = {
                Icon(
                    Icons.Default.Person,
                    contentDescription = null,
                    tint = Color.White.copy(alpha = 0.6f)
                )
            },
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Text,
                imeAction = ImeAction.Next
            ),
            keyboardActions = KeyboardActions(
                onNext = { focusManager.moveFocus(FocusDirection.Down) }
            ),
            colors = kagamiTextFieldColors(),
            modifier = Modifier
                .fillMaxWidth()
                .semantics {
                    contentDescription = "Username. Enter your Kagami username."
                }
        )

        Spacer(modifier = Modifier.height(16.dp))

        // Password Field
        OutlinedTextField(
            value = state.password,
            onValueChange = viewModel::updatePassword,
            label = { Text("Password") },
            singleLine = true,
            leadingIcon = {
                Icon(
                    Icons.Default.Lock,
                    contentDescription = null,
                    tint = Color.White.copy(alpha = 0.6f)
                )
            },
            trailingIcon = {
                IconButton(
                    onClick = {
                        view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                        passwordVisible = !passwordVisible
                    },
                    modifier = Modifier
                        .minTouchTarget()
                        .semantics {
                            contentDescription = if (passwordVisible) {
                                "Hide password"
                            } else {
                                "Show password"
                            }
                            role = Role.Button
                        }
                ) {
                    Icon(
                        imageVector = if (passwordVisible) {
                            Icons.Default.VisibilityOff
                        } else {
                            Icons.Default.Visibility
                        },
                        contentDescription = null,
                        tint = Color.White.copy(alpha = 0.6f)
                    )
                }
            },
            visualTransformation = if (passwordVisible) {
                VisualTransformation.None
            } else {
                PasswordVisualTransformation()
            },
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Done
            ),
            keyboardActions = KeyboardActions(
                onDone = {
                    focusManager.clearFocus()
                    if (!state.isLoading) {
                        view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                        viewModel.login(onLoginSuccess)
                    }
                }
            ),
            colors = kagamiTextFieldColors(),
            modifier = Modifier
                .fillMaxWidth()
                .semantics {
                    contentDescription = "Password. Enter your Kagami password."
                }
        )

        // Error Message
        if (state.error != null) {
            Spacer(modifier = Modifier.height(16.dp))
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics {
                        contentDescription = "Error: ${state.error}"
                    },
                colors = CardDefaults.cardColors(
                    containerColor = SafetyViolation.copy(alpha = 0.15f)
                ),
                shape = RoundedCornerShape(8.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.Default.Warning,
                        contentDescription = null,
                        tint = SafetyViolation,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = state.error ?: "",
                        style = MaterialTheme.typography.bodySmall,
                        color = SafetyViolation
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(32.dp))

        // Login Button
        Button(
            onClick = {
                view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                viewModel.login(onLoginSuccess)
            },
            enabled = !state.isLoading,
            colors = ButtonDefaults.buttonColors(
                containerColor = Crystal,
                contentColor = Void,
                disabledContainerColor = Crystal.copy(alpha = 0.5f),
                disabledContentColor = Void.copy(alpha = 0.5f)
            ),
            modifier = Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = MinTouchTargetSize)
                .semantics {
                    contentDescription = if (state.isLoading) {
                        "Signing in"
                    } else {
                        "Sign in to Kagami"
                    }
                    role = Role.Button
                }
        ) {
            if (state.isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    color = Void,
                    strokeWidth = 2.dp
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text("Signing In...")
            } else {
                Text(
                    text = "Sign In",
                    fontWeight = FontWeight.Medium
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Create Account Button
        TextButton(
            onClick = {
                view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                onCreateAccount()
            },
            modifier = Modifier
                .minTouchTarget()
                .semantics {
                    contentDescription = "Create a new Kagami account"
                    role = Role.Button
                }
        ) {
            Text(
                text = "Create Account",
                color = Crystal,
                style = MaterialTheme.typography.bodyMedium
            )
        }

        Spacer(modifier = Modifier.weight(1f))

        // Safety footer
        Text(
            text = stringResource(R.string.login_safety_footer),
            style = MaterialTheme.typography.bodySmall,
            color = Crystal.copy(alpha = 0.5f),
            textAlign = TextAlign.Center,
            modifier = Modifier
                .padding(bottom = 16.dp)
                .clearAndSetSemantics { }
        )
    }
}

// =============================================================================
// SERVER SELECTION DIALOG
// =============================================================================

@Composable
private fun ServerSelectionDialog(
    servers: List<String>,
    onSelect: (String) -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = VoidLight,
        title = {
            Text(
                text = "Select Server",
                color = Color.White,
                modifier = Modifier.semantics { heading() }
            )
        },
        text = {
            Column {
                Text(
                    text = "Found ${servers.size} Kagami server(s) on your network:",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White.copy(alpha = 0.7f)
                )
                Spacer(modifier = Modifier.height(16.dp))
                servers.forEach { server ->
                    Card(
                        onClick = { onSelect(server) },
                        colors = CardDefaults.cardColors(containerColor = Void),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                            .semantics {
                                contentDescription = "Select server $server"
                                role = Role.Button
                            }
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                Icons.Default.Cloud,
                                contentDescription = null,
                                tint = Crystal,
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                text = server,
                                style = MaterialTheme.typography.bodyMedium,
                                color = Color.White
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(
                onClick = onDismiss,
                modifier = Modifier.semantics {
                    contentDescription = "Cancel server selection"
                    role = Role.Button
                }
            ) {
                Text("Cancel", color = Color.White.copy(alpha = 0.6f))
            }
        }
    )
}

// =============================================================================
// HELPER COMPOSABLES
// =============================================================================

@Composable
private fun kagamiTextFieldColors() = OutlinedTextFieldDefaults.colors(
    focusedTextColor = Color.White,
    unfocusedTextColor = Color.White,
    focusedBorderColor = Crystal,
    unfocusedBorderColor = Color.White.copy(alpha = 0.3f),
    focusedLabelColor = Crystal,
    unfocusedLabelColor = Color.White.copy(alpha = 0.5f),
    cursorColor = Crystal,
    focusedPlaceholderColor = Color.White.copy(alpha = 0.4f),
    unfocusedPlaceholderColor = Color.White.copy(alpha = 0.3f),
    focusedLeadingIconColor = Crystal,
    unfocusedLeadingIconColor = Color.White.copy(alpha = 0.6f)
)

/*
 * Mirror
 * h(x) >= 0. Always.
 */
