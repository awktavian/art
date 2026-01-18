package com.kagami.wear.complications

import android.app.PendingIntent
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.drawable.Icon
import android.util.Log
import androidx.wear.watchface.complications.data.ComplicationData
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.data.LongTextComplicationData
import androidx.wear.watchface.complications.data.MonochromaticImage
import androidx.wear.watchface.complications.data.MonochromaticImageComplicationData
import androidx.wear.watchface.complications.data.PlainComplicationText
import androidx.wear.watchface.complications.data.RangedValueComplicationData
import androidx.wear.watchface.complications.data.ShortTextComplicationData
import androidx.wear.watchface.complications.data.SmallImage
import androidx.wear.watchface.complications.data.SmallImageComplicationData
import androidx.wear.watchface.complications.data.SmallImageType
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import com.kagami.wear.MainActivity
import com.kagami.wear.R
import com.kagami.wear.services.KagamiWearApiService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.runBlocking

/**
 * Kagami Complication Service - Watch Face Data
 *
 * Colony: Crystal (e7) - Verification
 *
 * Provides:
 * - Safety status for watch face complications
 * - Quick action tap to open app
 *
 * Supports:
 * - SHORT_TEXT: Brief status (OK, !, !!)
 * - LONG_TEXT: Full status with room context
 * - RANGED_VALUE: Safety score as gauge (0-100%)
 * - SMALL_IMAGE: Kagami icon
 * - MONOCHROMATIC_IMAGE: Simple icon for watch faces
 */
class KagamiComplicationService : ComplicationDataSourceService() {

    private val serviceJob = SupervisorJob()
    private val serviceScope = CoroutineScope(Dispatchers.IO + serviceJob)

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
        serviceJob.cancel()
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData? {
        return when (type) {
            ComplicationType.SHORT_TEXT -> createShortTextComplication(
                text = "Secure",
                contentDescription = "Home is secure"
            )
            ComplicationType.LONG_TEXT -> createLongTextComplication(
                title = "Home",
                text = "Secure - All systems OK",
                contentDescription = "Home is secure, all systems operating normally"
            )
            ComplicationType.RANGED_VALUE -> createRangedValueComplication(
                value = 0.85f,
                text = "85%",
                contentDescription = "Safety score 85 percent"
            )
            ComplicationType.SMALL_IMAGE -> createSmallImageComplication()
            ComplicationType.MONOCHROMATIC_IMAGE -> createMonochromaticImageComplication()
            else -> null
        }
    }

    override fun onComplicationRequest(
        request: ComplicationRequest,
        listener: ComplicationRequestListener
    ) {
        // Fetch current status (blocking for complication)
        val health = runBlocking {
            try {
                KagamiWearApiService.fetchHealth()
            } catch (e: Exception) {
                null
            }
        }

        val complicationData = when (request.complicationType) {
            ComplicationType.SHORT_TEXT -> {
                val (text, description) = getStatusText(health?.safetyScore)
                createShortTextComplication(text, description)
            }
            ComplicationType.LONG_TEXT -> {
                val (statusText, description) = getStatusText(health?.safetyScore)
                val fullText = if (health?.isConnected == true && health.safetyScore != null) {
                    "$statusText - ${getContextText(health.safetyScore)}"
                } else {
                    "Disconnected"
                }
                createLongTextComplication(
                    title = "Kagami",
                    text = fullText,
                    contentDescription = description
                )
            }
            ComplicationType.RANGED_VALUE -> {
                val score = health?.safetyScore?.toFloat() ?: 0f
                val percentage = (score * 100).toInt()
                createRangedValueComplication(
                    value = score,
                    text = if (health?.isConnected == true) "$percentage%" else "--",
                    contentDescription = if (health?.isConnected == true)
                        "Safety score $percentage percent"
                    else
                        "Disconnected"
                )
            }
            ComplicationType.SMALL_IMAGE -> {
                createSmallImageComplication()
            }
            ComplicationType.MONOCHROMATIC_IMAGE -> {
                createMonochromaticImageComplication()
            }
            else -> null
        }

        listener.onComplicationData(complicationData)
    }

    private fun getStatusText(score: Double?): Pair<String, String> {
        return when {
            score == null -> "?" to "Status unknown"
            score >= 0.7 -> "OK" to "Home is secure"
            score >= 0.3 -> "!" to "Attention needed"
            else -> "!!" to "Action required"
        }
    }

    private fun getContextText(score: Double): String {
        return when {
            score >= 0.9 -> "All systems optimal"
            score >= 0.7 -> "All systems OK"
            score >= 0.5 -> "Minor issues"
            score >= 0.3 -> "Needs attention"
            else -> "Action required"
        }
    }

    private fun createShortTextComplication(
        text: String,
        contentDescription: String
    ): ComplicationData {
        return ShortTextComplicationData.Builder(
            text = PlainComplicationText.Builder(text).build(),
            contentDescription = PlainComplicationText.Builder(contentDescription).build()
        )
            .setTapAction(createTapPendingIntent())
            .build()
    }

    private fun createLongTextComplication(
        title: String,
        text: String,
        contentDescription: String
    ): ComplicationData {
        return LongTextComplicationData.Builder(
            text = PlainComplicationText.Builder(text).build(),
            contentDescription = PlainComplicationText.Builder(contentDescription).build()
        )
            .setTitle(PlainComplicationText.Builder(title).build())
            .setSmallImage(
                SmallImage.Builder(
                    image = Icon.createWithResource(this, R.drawable.ic_complication),
                    type = SmallImageType.ICON
                ).build()
            )
            .setTapAction(createTapPendingIntent())
            .build()
    }

    private fun createRangedValueComplication(
        value: Float,
        text: String,
        contentDescription: String
    ): ComplicationData {
        return RangedValueComplicationData.Builder(
            value = value,
            min = 0f,
            max = 1f,
            contentDescription = PlainComplicationText.Builder(contentDescription).build()
        )
            .setText(PlainComplicationText.Builder(text).build())
            .setTapAction(createTapPendingIntent())
            .build()
    }

    private fun createSmallImageComplication(): ComplicationData {
        return SmallImageComplicationData.Builder(
            smallImage = SmallImage.Builder(
                image = Icon.createWithResource(this, R.drawable.ic_complication),
                type = SmallImageType.ICON
            ).build(),
            contentDescription = PlainComplicationText.Builder("Kagami home control").build()
        )
            .setTapAction(createTapPendingIntent())
            .build()
    }

    private fun createMonochromaticImageComplication(): ComplicationData {
        return MonochromaticImageComplicationData.Builder(
            monochromaticImage = MonochromaticImage.Builder(
                image = Icon.createWithResource(this, R.drawable.ic_complication)
            ).build(),
            contentDescription = PlainComplicationText.Builder("Kagami home control").build()
        )
            .setTapAction(createTapPendingIntent())
            .build()
    }

    private fun createTapPendingIntent(): PendingIntent {
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("complication_action", "refresh_status")
        }
        return PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    companion object {
        private const val TAG = "KagamiComplication"

        /**
         * Request an update for all Kagami complications.
         * Call this when home status changes significantly.
         *
         * @param context Application context
         */
        fun requestUpdate(context: Context) {
            try {
                val requester = ComplicationDataSourceUpdateRequester.create(
                    context,
                    ComponentName(context, KagamiComplicationService::class.java)
                )
                requester.requestUpdateAll()
                Log.d(TAG, "Requested complication update")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to request complication update", e)
            }
        }

        /**
         * Request an update for a specific complication ID.
         *
         * @param context Application context
         * @param complicationId The specific complication to update
         */
        fun requestUpdate(context: Context, complicationId: Int) {
            try {
                val requester = ComplicationDataSourceUpdateRequester.create(
                    context,
                    ComponentName(context, KagamiComplicationService::class.java)
                )
                requester.requestUpdate(complicationId)
                Log.d(TAG, "Requested complication update for ID: $complicationId")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to request complication update", e)
            }
        }
    }
}
