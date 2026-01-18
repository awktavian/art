/**
 * Kagami Search View - Unified Search Component
 *
 * Colony: Nexus (e4) - Integration
 *
 * P1: Unified search for rooms, scenes, and settings.
 * - Typeahead suggestions
 * - Recent searches
 * - Voice input support
 *
 * Accessibility:
 * - TalkBack content descriptions
 * - Minimum 48dp touch targets
 * - Clear button accessibility
 */

package com.kagami.android.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.kagami.android.ui.MinTouchTargetSize
import com.kagami.android.ui.minTouchTarget
import com.kagami.android.ui.theme.Crystal
import com.kagami.android.ui.theme.VoidLight

/**
 * Search result types.
 */
enum class SearchResultType {
    ROOM,
    SCENE,
    SETTING
}

/**
 * Search result data class.
 */
data class SearchResult(
    val id: String,
    val name: String,
    val description: String,
    val type: SearchResultType,
    val icon: ImageVector = when (type) {
        SearchResultType.ROOM -> Icons.Default.Home
        SearchResultType.SCENE -> Icons.Default.Movie
        SearchResultType.SETTING -> Icons.Default.Settings
    }
)

/**
 * Unified search bar with typeahead suggestions.
 *
 * @param query Current search query
 * @param onQueryChange Callback when query changes
 * @param onSearch Callback when search is submitted
 * @param onResultClick Callback when a result is clicked
 * @param results Current search results
 * @param recentSearches Recent search terms
 * @param modifier Modifier for the search bar
 * @param placeholder Placeholder text
 * @param showResults Whether to show the results dropdown
 */
@Composable
fun SearchBar(
    query: String,
    onQueryChange: (String) -> Unit,
    onSearch: (String) -> Unit,
    onResultClick: (SearchResult) -> Unit,
    results: List<SearchResult> = emptyList(),
    recentSearches: List<String> = emptyList(),
    modifier: Modifier = Modifier,
    placeholder: String = "Search rooms, scenes, settings...",
    showResults: Boolean = true
) {
    var isFocused by remember { mutableStateOf(false) }
    val focusRequester = remember { FocusRequester() }
    val keyboardController = LocalSoftwareKeyboardController.current

    Column(modifier = modifier) {
        OutlinedTextField(
            value = query,
            onValueChange = onQueryChange,
            modifier = Modifier
                .fillMaxWidth()
                .focusRequester(focusRequester)
                .onFocusChanged { isFocused = it.isFocused }
                .semantics {
                    contentDescription = "Search. $placeholder"
                },
            placeholder = {
                Text(
                    text = placeholder,
                    color = Color.White.copy(alpha = 0.5f)
                )
            },
            leadingIcon = {
                Icon(
                    imageVector = Icons.Default.Search,
                    contentDescription = null,
                    tint = Crystal
                )
            },
            trailingIcon = {
                if (query.isNotEmpty()) {
                    IconButton(
                        onClick = { onQueryChange("") },
                        modifier = Modifier
                            .minTouchTarget()
                            .semantics {
                                contentDescription = "Clear search"
                                role = Role.Button
                            }
                    ) {
                        Icon(
                            imageVector = Icons.Default.Clear,
                            contentDescription = null,
                            tint = Color.White.copy(alpha = 0.5f)
                        )
                    }
                }
            },
            keyboardOptions = KeyboardOptions(
                imeAction = ImeAction.Search
            ),
            keyboardActions = KeyboardActions(
                onSearch = {
                    onSearch(query)
                    keyboardController?.hide()
                }
            ),
            singleLine = true,
            shape = RoundedCornerShape(12.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedContainerColor = VoidLight,
                unfocusedContainerColor = VoidLight,
                focusedBorderColor = Crystal,
                unfocusedBorderColor = Color.Transparent,
                cursorColor = Crystal,
                focusedTextColor = Color.White,
                unfocusedTextColor = Color.White
            )
        )

        // Results dropdown
        AnimatedVisibility(
            visible = showResults && isFocused && (results.isNotEmpty() || (query.isEmpty() && recentSearches.isNotEmpty())),
            enter = fadeIn() + expandVertically(),
            exit = fadeOut() + shrinkVertically()
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(VoidLight)
            ) {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(8.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    // Show recent searches when query is empty
                    if (query.isEmpty() && recentSearches.isNotEmpty()) {
                        items(recentSearches.take(5)) { search ->
                            RecentSearchItem(
                                text = search,
                                onClick = { onQueryChange(search) }
                            )
                        }
                    }

                    // Show search results
                    items(results.take(10)) { result ->
                        SearchResultItem(
                            result = result,
                            onClick = {
                                onResultClick(result)
                                keyboardController?.hide()
                            }
                        )
                    }
                }
            }
        }
    }
}

/**
 * Individual search result item.
 */
@Composable
private fun SearchResultItem(
    result: SearchResult,
    onClick: () -> Unit
) {
    val typeLabel = when (result.type) {
        SearchResultType.ROOM -> "Room"
        SearchResultType.SCENE -> "Scene"
        SearchResultType.SETTING -> "Setting"
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .clickable(
                onClick = onClick,
                role = Role.Button
            )
            .padding(12.dp)
            .semantics {
                contentDescription = "$typeLabel: ${result.name}. ${result.description}"
                role = Role.Button
            },
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = result.icon,
            contentDescription = null,
            tint = Crystal,
            modifier = Modifier.size(24.dp)
        )

        Spacer(modifier = Modifier.width(12.dp))

        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = result.name,
                style = MaterialTheme.typography.bodyMedium,
                color = Color.White
            )
            Text(
                text = result.description,
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.6f)
            )
        }

        Text(
            text = typeLabel,
            style = MaterialTheme.typography.labelSmall,
            color = Crystal.copy(alpha = 0.7f)
        )
    }
}

/**
 * Recent search item.
 */
@Composable
private fun RecentSearchItem(
    text: String,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .clickable(
                onClick = onClick,
                role = Role.Button
            )
            .padding(12.dp)
            .semantics {
                contentDescription = "Recent search: $text"
                role = Role.Button
            },
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = Icons.Default.History,
            contentDescription = null,
            tint = Color.White.copy(alpha = 0.5f),
            modifier = Modifier.size(20.dp)
        )

        Spacer(modifier = Modifier.width(12.dp))

        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = Color.White.copy(alpha = 0.8f)
        )
    }
}

/**
 * Compact search icon button for top app bars.
 */
@Composable
fun SearchIconButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    IconButton(
        onClick = onClick,
        modifier = modifier
            .minTouchTarget()
            .semantics {
                contentDescription = "Open search"
                role = Role.Button
            }
    ) {
        Icon(
            imageVector = Icons.Default.Search,
            contentDescription = null,
            tint = Crystal
        )
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
