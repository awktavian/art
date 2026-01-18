/**
 * Test Models for Screenshot Testing
 *
 * Simplified data models used in screenshot tests.
 * These mirror the production models but are decoupled for testing.
 *
 * h(x) >= 0. Always.
 */
package com.kagami.android.ui.screens

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector

/**
 * Scene model for testing.
 */
data class Scene(
    val id: String,
    val name: String,
    val description: String,
    val icon: ImageVector,
    val color: Color
)

/*
 * Mirror
 * h(x) >= 0. Always.
 */
