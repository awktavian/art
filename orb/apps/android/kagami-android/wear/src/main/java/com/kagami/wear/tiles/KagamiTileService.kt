package com.kagami.wear.tiles

import android.content.Context
import android.util.Log
import androidx.wear.protolayout.ActionBuilders
import androidx.wear.protolayout.ColorBuilders.argb
import androidx.wear.protolayout.DeviceParametersBuilders
import androidx.wear.protolayout.DimensionBuilders.*
import androidx.wear.protolayout.LayoutElementBuilders
import androidx.wear.protolayout.LayoutElementBuilders.*
import androidx.wear.protolayout.ModifiersBuilders.*
import androidx.wear.protolayout.ResourceBuilders.Resources
import androidx.wear.protolayout.TimelineBuilders.*
import androidx.wear.protolayout.material.layouts.PrimaryLayout
import androidx.wear.tiles.RequestBuilders
import androidx.wear.tiles.TileBuilders
import androidx.wear.tiles.TileService
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.guava.future
import java.time.LocalTime

/**
 * Kagami Tile Service - Quick Actions Tile
 *
 * Colony: Beacon (e5) - Planning
 *
 * Tile Features:
 * - Context-aware hero action
 * - Safety score display
 * - Quick scene buttons
 * - Auto-refresh every 15 minutes
 */
class KagamiTileService : TileService() {

    // Use SupervisorJob for proper cancellation
    private val serviceJob = SupervisorJob()
    private val serviceScope = CoroutineScope(Dispatchers.IO + serviceJob)

    companion object {
        private const val TAG = "KagamiTile"
        private const val RESOURCES_VERSION = "1"

        // Clickable IDs
        private const val ID_MOVIE_MODE = "movie_mode"
        private const val ID_GOODNIGHT = "goodnight"
        private const val ID_LIGHTS_ON = "lights_on"
        private const val ID_LIGHTS_OFF = "lights_off"

        // Colors
        private const val COLOR_CRYSTAL = 0xFF67D4E4.toInt()
        private const val COLOR_FORGE = 0xFFD4AF37.toInt()
        private const val COLOR_FLOW = 0xFF4ECDC4.toInt()
        private const val COLOR_BEACON = 0xFFF59E0B.toInt()
        private const val COLOR_SAFETY_OK = 0xFF00FF88.toInt()

        /**
         * Request a tile update. Call this when home status changes.
         *
         * @param context Application context
         */
        fun requestTileUpdate(context: Context) {
            try {
                TileService.getUpdater(context)
                    .requestUpdate(KagamiTileService::class.java)
                Log.d(TAG, "Requested tile update")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to request tile update", e)
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        // Cancel all coroutines to prevent leaks
        serviceScope.cancel()
        serviceJob.cancel()
    }

    override fun onTileRequest(requestParams: RequestBuilders.TileRequest): ListenableFuture<TileBuilders.Tile> {
        return serviceScope.future {
            buildTile(requestParams)
        }
    }

    private suspend fun buildTile(requestParams: RequestBuilders.TileRequest): TileBuilders.Tile {
        val heroAction = getContextualHeroAction()

        return TileBuilders.Tile.Builder()
            .setResourcesVersion(RESOURCES_VERSION)
            .setFreshnessIntervalMillis(15 * 60 * 1000) // 15 minutes
            .setTileTimeline(
                Timeline.Builder()
                    .addTimelineEntry(
                        TimelineEntry.Builder()
                            .setLayout(
                                Layout.Builder()
                                    .setRoot(buildLayout(heroAction))
                                    .build()
                            )
                            .build()
                    )
                    .build()
            )
            .build()
    }

    private fun buildLayout(heroAction: HeroAction): LayoutElement {
        val deviceParams = DeviceParametersBuilders.DeviceParameters.Builder()
            .setScreenWidthDp(200)
            .setScreenHeightDp(200)
            .build()

        return PrimaryLayout.Builder(deviceParams)
            .setContent(
                Column.Builder()
                    .setWidth(expand())
                    .setHeight(expand())
                    .setHorizontalAlignment(HORIZONTAL_ALIGN_CENTER)
                    .addContent(buildHeader())
                    .addContent(buildHeroButton(heroAction))
                    .addContent(buildQuickActions())
                    .build()
            )
            .build()
    }

    private fun buildHeader(): LayoutElement {
        return Row.Builder()
            .setWidth(expand())
            .setVerticalAlignment(VERTICAL_ALIGN_CENTER)
            .setModifiers(
                Modifiers.Builder()
                    .setSemantics(
                        Semantics.Builder()
                            .setContentDescription("Kagami smart home control")
                            .build()
                    )
                    .build()
            )
            .addContent(
                LayoutElementBuilders.Text.Builder()
                    .setText("Kagami")
                    .setFontStyle(
                        FontStyle.Builder()
                            .setSize(sp(14f))
                            .setColor(argb(0xFFFFFFFF.toInt()))
                            .build()
                    )
                    .build()
            )
            .build()
    }

    private fun buildHeroButton(heroAction: HeroAction): LayoutElement {
        return Box.Builder()
            .setWidth(expand())
            .setHeight(dp(60f))
            .setHorizontalAlignment(HORIZONTAL_ALIGN_CENTER)
            .setVerticalAlignment(VERTICAL_ALIGN_CENTER)
            .setModifiers(
                Modifiers.Builder()
                    .setSemantics(
                        Semantics.Builder()
                            .setContentDescription("${heroAction.label}. Tap to activate")
                            .build()
                    )
                    .setClickable(
                        Clickable.Builder()
                            .setId(heroAction.id)
                            .setOnClick(
                                ActionBuilders.LaunchAction.Builder()
                                    .setAndroidActivity(
                                        ActionBuilders.AndroidActivity.Builder()
                                            .setPackageName(packageName)
                                            .setClassName("$packageName.MainActivity")
                                            .addKeyToExtraMapping(
                                                "scene",
                                                ActionBuilders.AndroidStringExtra.Builder()
                                                    .setValue(heroAction.id)
                                                    .build()
                                            )
                                            .build()
                                    )
                                    .build()
                            )
                            .build()
                    )
                    .setBackground(
                        Background.Builder()
                            .setColor(argb(heroAction.color))
                            .setCorner(Corner.Builder().setRadius(dp(16f)).build())
                            .build()
                    )
                    .setPadding(
                        Padding.Builder()
                            .setAll(dp(12f))
                            .build()
                    )
                    .build()
            )
            .addContent(
                Column.Builder()
                    .setHorizontalAlignment(HORIZONTAL_ALIGN_CENTER)
                    .addContent(
                        LayoutElementBuilders.Text.Builder()
                            .setText(heroAction.label)
                            .setFontStyle(
                                FontStyle.Builder()
                                    .setSize(sp(14f))
                                    .setColor(argb(0xFFFFFFFF.toInt()))
                                    .setWeight(FONT_WEIGHT_MEDIUM)
                                    .build()
                            )
                            .build()
                    )
                    .build()
            )
            .build()
    }

    private fun buildQuickActions(): LayoutElement {
        return Row.Builder()
            .setWidth(expand())
            .addContent(buildQuickActionChip("Lights On", ID_LIGHTS_ON, COLOR_BEACON))
            .addContent(Spacer.Builder().setWidth(dp(8f)).build())
            .addContent(buildQuickActionChip("Lights Off", ID_LIGHTS_OFF, COLOR_FLOW))
            .build()
    }

    private fun buildQuickActionChip(
        label: String,
        clickableId: String,
        color: Int
    ): LayoutElement {
        return Box.Builder()
            .setWidth(expand())
            .setHeight(dp(36f))
            .setHorizontalAlignment(HORIZONTAL_ALIGN_CENTER)
            .setVerticalAlignment(VERTICAL_ALIGN_CENTER)
            .setModifiers(
                Modifiers.Builder()
                    .setSemantics(
                        Semantics.Builder()
                            .setContentDescription("$label. Tap to activate")
                            .build()
                    )
                    .setClickable(
                        Clickable.Builder()
                            .setId(clickableId)
                            .setOnClick(
                                ActionBuilders.LaunchAction.Builder()
                                    .setAndroidActivity(
                                        ActionBuilders.AndroidActivity.Builder()
                                            .setPackageName(packageName)
                                            .setClassName("$packageName.MainActivity")
                                            .addKeyToExtraMapping(
                                                "action",
                                                ActionBuilders.AndroidStringExtra.Builder()
                                                    .setValue(clickableId)
                                                    .build()
                                            )
                                            .build()
                                    )
                                    .build()
                            )
                            .build()
                    )
                    .setBackground(
                        Background.Builder()
                            .setColor(argb(color and 0x40FFFFFF))
                            .setCorner(Corner.Builder().setRadius(dp(8f)).build())
                            .build()
                    )
                    .build()
            )
            .addContent(
                LayoutElementBuilders.Text.Builder()
                    .setText(label)
                    .setFontStyle(
                        FontStyle.Builder()
                            .setSize(sp(10f))
                            .setColor(argb(0xFFFFFFFF.toInt()))
                            .build()
                    )
                    .build()
            )
            .build()
    }

    override fun onTileResourcesRequest(requestParams: RequestBuilders.ResourcesRequest): ListenableFuture<Resources> {
        return Futures.immediateFuture(
            Resources.Builder()
                .setVersion(RESOURCES_VERSION)
                .build()
        )
    }

    private fun getContextualHeroAction(): HeroAction {
        val hour = LocalTime.now().hour

        return when (hour) {
            in 5..8 -> HeroAction("Morning", "good_morning", COLOR_BEACON and 0x60FFFFFF)
            in 9..16 -> HeroAction("Focus", "focus", COLOR_SAFETY_OK and 0x60FFFFFF)
            in 17..20 -> HeroAction("Movie Mode", ID_MOVIE_MODE, COLOR_FORGE and 0x60FFFFFF)
            in 21..23 -> HeroAction("Goodnight", ID_GOODNIGHT, COLOR_FLOW and 0x60FFFFFF)
            else -> HeroAction("Sleep", "sleep", COLOR_FLOW and 0x60FFFFFF)
        }
    }

    private data class HeroAction(
        val label: String,
        val id: String,
        val color: Int
    )
}
