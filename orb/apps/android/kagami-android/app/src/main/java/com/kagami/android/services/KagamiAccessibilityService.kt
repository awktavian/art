/**
 * KagamiAccessibilityService — Full Device Control via Accessibility API
 *
 * Capabilities when enabled:
 *   - Read screen content (all app UIs)
 *   - Perform gestures (tap, swipe, scroll)
 *   - Inject key events
 *   - Control display (magnification)
 *   - Take screenshots (Android 9+)
 *   - Control soft keyboard
 *
 * Safety:
 *   - All actions are logged
 *   - Rate-limited to prevent runaway automation
 *   - Emergency stop via notification action
 *   - User must explicitly enable in Settings
 */

package com.kagami.android.services

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.accessibilityservice.GestureDescription
import android.content.Intent
import android.graphics.Path
import android.graphics.PixelFormat
import android.graphics.Rect
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/**
 * Accessibility service providing full device control capabilities.
 *
 * This service enables Kagami to:
 * - Read any app's UI tree
 * - Perform taps, swipes, and gestures
 * - Type text into any field
 * - Navigate between apps
 * - Take screenshots
 *
 * Must be enabled by user in Settings > Accessibility > Kagami.
 */
class KagamiAccessibilityService : AccessibilityService() {

    companion object {
        private const val TAG = "KagamiA11y"

        // Rate limiting
        private const val MAX_ACTIONS_PER_SECOND = 20
        private val actionsThisSecond = AtomicLong(0)
        private val lastRateReset = AtomicLong(0)

        // Emergency stop
        private val emergencyStop = AtomicBoolean(false)

        // Service instance for external access
        private var instance: KagamiAccessibilityService? = null

        /**
         * Get the service instance if running.
         */
        fun getInstance(): KagamiAccessibilityService? = instance

        /**
         * Check if the service is currently running.
         */
        fun isRunning(): Boolean = instance != null

        /**
         * Emergency stop - halt all automation.
         */
        fun emergencyStop() {
            emergencyStop.set(true)
            Log.w(TAG, "🛑 Emergency stop activated")
        }

        /**
         * Resume automation after emergency stop.
         */
        fun resume() {
            emergencyStop.set(false)
            Log.i(TAG, "✅ Automation resumed")
        }

        /**
         * Check if emergency stop is active.
         */
        fun isStopped(): Boolean = emergencyStop.get()
    }

    // State
    private val _isEnabled = MutableStateFlow(false)
    val isEnabled: StateFlow<Boolean> = _isEnabled

    private val _currentPackage = MutableStateFlow<String?>(null)
    val currentPackage: StateFlow<String?> = _currentPackage

    private val _currentActivity = MutableStateFlow<String?>(null)
    val currentActivity: StateFlow<String?> = _currentActivity

    private val serviceScope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    // ============================================================================
    // Lifecycle
    // ============================================================================

    override fun onServiceConnected() {
        super.onServiceConnected()

        Log.i(TAG, "🔗 Kagami Accessibility Service connected")
        instance = this
        _isEnabled.value = true

        // Configure service capabilities
        serviceInfo = serviceInfo.apply {
            // Event types to monitor
            eventTypes = AccessibilityEvent.TYPES_ALL_MASK

            // Feedback type
            feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC

            // Flags for capabilities
            flags = AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS or
                    AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS or
                    AccessibilityServiceInfo.FLAG_REQUEST_TOUCH_EXPLORATION_MODE or
                    AccessibilityServiceInfo.FLAG_REQUEST_ENHANCED_WEB_ACCESSIBILITY or
                    AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS

            // No package filter - monitor all apps
            packageNames = null

            // Notification timeout
            notificationTimeout = 100
        }

        // Notify Kagami backend that accessibility is now available
        notifyBackend("accessibility_enabled")
    }

    override fun onInterrupt() {
        Log.w(TAG, "⚠️ Kagami Accessibility Service interrupted")
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.i(TAG, "🔌 Kagami Accessibility Service destroyed")
        instance = null
        _isEnabled.value = false
        serviceScope.cancel()
    }

    // ============================================================================
    // Event Handling
    // ============================================================================

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        event ?: return

        when (event.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                _currentPackage.value = event.packageName?.toString()
                _currentActivity.value = event.className?.toString()

                Log.d(TAG, "Window: ${event.packageName} / ${event.className}")
            }

            AccessibilityEvent.TYPE_VIEW_FOCUSED -> {
                // Track focus changes for context awareness
                Log.v(TAG, "Focus: ${event.className} in ${event.packageName}")
            }

            AccessibilityEvent.TYPE_VIEW_CLICKED -> {
                // Track clicks for understanding user patterns
                Log.v(TAG, "Click: ${event.className}")
            }

            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED -> {
                // Track text input (be careful with sensitive data!)
                Log.v(TAG, "Text changed in ${event.className}")
            }

            AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED -> {
                // Track notifications
                val text = event.text.joinToString(" ")
                Log.d(TAG, "Notification from ${event.packageName}: $text")
            }
        }
    }

    // ============================================================================
    // Screen Reading
    // ============================================================================

    /**
     * Get the entire UI tree of the current screen.
     */
    fun getScreenContent(): List<NodeInfo> {
        val nodes = mutableListOf<NodeInfo>()
        val rootNode = rootInActiveWindow ?: return nodes

        try {
            traverseNode(rootNode, nodes, 0)
        } finally {
            rootNode.recycle()
        }

        return nodes
    }

    /**
     * Recursively traverse the accessibility tree.
     */
    private fun traverseNode(node: AccessibilityNodeInfo, nodes: MutableList<NodeInfo>, depth: Int) {
        if (depth > 50) return // Prevent infinite recursion

        val bounds = Rect()
        node.getBoundsInScreen(bounds)

        nodes.add(NodeInfo(
            id = node.viewIdResourceName,
            className = node.className?.toString() ?: "",
            text = node.text?.toString(),
            contentDescription = node.contentDescription?.toString(),
            isClickable = node.isClickable,
            isEditable = node.isEditable,
            isChecked = node.isChecked,
            isEnabled = node.isEnabled,
            isFocused = node.isFocused,
            bounds = bounds,
            depth = depth
        ))

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            try {
                traverseNode(child, nodes, depth + 1)
            } finally {
                child.recycle()
            }
        }
    }

    /**
     * Find a node by text content.
     */
    fun findNodeByText(text: String): AccessibilityNodeInfo? {
        val rootNode = rootInActiveWindow ?: return null
        val nodes = rootNode.findAccessibilityNodeInfosByText(text)
        return nodes.firstOrNull()
    }

    /**
     * Find a node by view ID.
     */
    fun findNodeById(viewId: String): AccessibilityNodeInfo? {
        val rootNode = rootInActiveWindow ?: return null
        val nodes = rootNode.findAccessibilityNodeInfosByViewId(viewId)
        return nodes.firstOrNull()
    }

    // ============================================================================
    // Actions
    // ============================================================================

    /**
     * Check rate limit before performing action.
     */
    private fun checkRateLimit(): Boolean {
        val now = System.currentTimeMillis() / 1000
        val lastReset = lastRateReset.get()

        if (now > lastReset) {
            lastRateReset.set(now)
            actionsThisSecond.set(0)
        }

        return actionsThisSecond.incrementAndGet() <= MAX_ACTIONS_PER_SECOND
    }

    /**
     * Perform a tap at screen coordinates.
     */
    fun tap(x: Float, y: Float): Boolean {
        if (emergencyStop.get()) {
            Log.w(TAG, "Tap blocked - emergency stop active")
            return false
        }

        if (!checkRateLimit()) {
            Log.w(TAG, "Tap blocked - rate limit exceeded")
            return false
        }

        Log.d(TAG, "Tap at ($x, $y)")

        val path = Path().apply {
            moveTo(x, y)
        }

        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 100))
            .build()

        return dispatchGesture(gesture, null, null)
    }

    /**
     * Perform a swipe gesture.
     */
    fun swipe(
        startX: Float,
        startY: Float,
        endX: Float,
        endY: Float,
        durationMs: Long = 300
    ): Boolean {
        if (emergencyStop.get()) {
            Log.w(TAG, "Swipe blocked - emergency stop active")
            return false
        }

        if (!checkRateLimit()) {
            Log.w(TAG, "Swipe blocked - rate limit exceeded")
            return false
        }

        Log.d(TAG, "Swipe from ($startX, $startY) to ($endX, $endY)")

        val path = Path().apply {
            moveTo(startX, startY)
            lineTo(endX, endY)
        }

        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, durationMs))
            .build()

        return dispatchGesture(gesture, null, null)
    }

    /**
     * Perform a long press at coordinates.
     */
    fun longPress(x: Float, y: Float, durationMs: Long = 1000): Boolean {
        if (emergencyStop.get()) {
            Log.w(TAG, "Long press blocked - emergency stop active")
            return false
        }

        if (!checkRateLimit()) {
            Log.w(TAG, "Long press blocked - rate limit exceeded")
            return false
        }

        Log.d(TAG, "Long press at ($x, $y) for ${durationMs}ms")

        val path = Path().apply {
            moveTo(x, y)
        }

        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, durationMs))
            .build()

        return dispatchGesture(gesture, null, null)
    }

    /**
     * Click on a specific node.
     */
    fun clickNode(node: AccessibilityNodeInfo): Boolean {
        if (emergencyStop.get()) {
            Log.w(TAG, "Click blocked - emergency stop active")
            return false
        }

        if (!checkRateLimit()) {
            Log.w(TAG, "Click blocked - rate limit exceeded")
            return false
        }

        Log.d(TAG, "Click on ${node.className}: ${node.text ?: node.contentDescription}")

        return node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
    }

    /**
     * Type text into the currently focused field.
     */
    fun typeText(text: String): Boolean {
        if (emergencyStop.get()) {
            Log.w(TAG, "Type blocked - emergency stop active")
            return false
        }

        val node = findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: return false

        Log.d(TAG, "Typing ${text.length} characters")

        val arguments = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        }

        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments)
    }

    /**
     * Press the back button.
     */
    fun pressBack(): Boolean {
        if (emergencyStop.get()) return false
        Log.d(TAG, "Press back")
        return performGlobalAction(GLOBAL_ACTION_BACK)
    }

    /**
     * Press the home button.
     */
    fun pressHome(): Boolean {
        if (emergencyStop.get()) return false
        Log.d(TAG, "Press home")
        return performGlobalAction(GLOBAL_ACTION_HOME)
    }

    /**
     * Press the recents button.
     */
    fun pressRecents(): Boolean {
        if (emergencyStop.get()) return false
        Log.d(TAG, "Press recents")
        return performGlobalAction(GLOBAL_ACTION_RECENTS)
    }

    /**
     * Open notifications.
     */
    fun openNotifications(): Boolean {
        if (emergencyStop.get()) return false
        Log.d(TAG, "Open notifications")
        return performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
    }

    /**
     * Open quick settings.
     */
    fun openQuickSettings(): Boolean {
        if (emergencyStop.get()) return false
        Log.d(TAG, "Open quick settings")
        return performGlobalAction(GLOBAL_ACTION_QUICK_SETTINGS)
    }

    /**
     * Take a screenshot (Android 9+).
     */
    fun takeScreenshot(): Boolean {
        if (emergencyStop.get()) return false

        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            Log.d(TAG, "Taking screenshot")
            performGlobalAction(GLOBAL_ACTION_TAKE_SCREENSHOT)
        } else {
            Log.w(TAG, "Screenshot not supported on this Android version")
            false
        }
    }

    /**
     * Lock the screen (Android 9+).
     */
    fun lockScreen(): Boolean {
        if (emergencyStop.get()) return false

        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            Log.d(TAG, "Locking screen")
            performGlobalAction(GLOBAL_ACTION_LOCK_SCREEN)
        } else {
            Log.w(TAG, "Lock screen not supported on this Android version")
            false
        }
    }

    /**
     * Scroll forward in current view.
     */
    fun scrollForward(): Boolean {
        if (emergencyStop.get()) return false

        val rootNode = rootInActiveWindow ?: return false
        val scrollable = findScrollableNode(rootNode)

        return scrollable?.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD) ?: false
    }

    /**
     * Scroll backward in current view.
     */
    fun scrollBackward(): Boolean {
        if (emergencyStop.get()) return false

        val rootNode = rootInActiveWindow ?: return false
        val scrollable = findScrollableNode(rootNode)

        return scrollable?.performAction(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD) ?: false
    }

    /**
     * Find a scrollable node in the tree.
     */
    private fun findScrollableNode(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (node.isScrollable) return node

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            val result = findScrollableNode(child)
            if (result != null) return result
        }

        return null
    }

    // ============================================================================
    // Backend Communication
    // ============================================================================

    /**
     * Notify Kagami backend of accessibility events.
     */
    private fun notifyBackend(event: String) {
        serviceScope.launch {
            try {
                // Send to Kagami API
                val apiService = KagamiApiService.getInstance()
                apiService?.reportAccessibilityEvent(event, currentPackage.value, currentActivity.value)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to notify backend: ${e.message}")
            }
        }
    }

    // ============================================================================
    // Data Classes
    // ============================================================================

    /**
     * Simplified node information for API responses.
     */
    data class NodeInfo(
        val id: String?,
        val className: String,
        val text: String?,
        val contentDescription: String?,
        val isClickable: Boolean,
        val isEditable: Boolean,
        val isChecked: Boolean,
        val isEnabled: Boolean,
        val isFocused: Boolean,
        val bounds: Rect,
        val depth: Int
    )
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * Accessibility is power.
 * Use it to help, not to harm.
 * Every action is logged.
 * The user remains in control.
 */
