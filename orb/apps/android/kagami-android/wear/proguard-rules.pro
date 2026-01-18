# Kagami Wear OS ProGuard Rules
#
# Colony: Crystal (e7) - Verification

# Keep Wear OS components
-keep class androidx.wear.** { *; }
-keep class com.google.android.gms.wearable.** { *; }

# Keep Compose
-keep class androidx.compose.** { *; }

# Keep Tiles
-keep class androidx.wear.tiles.** { *; }
-keep class androidx.wear.protolayout.** { *; }

# Keep Complications
-keep class androidx.wear.watchface.complications.** { *; }

# Keep OkHttp
-dontwarn okhttp3.**
-keep class okhttp3.** { *; }

# Keep Moshi
-keep class com.squareup.moshi.** { *; }

# Keep data classes
-keep class com.kagami.wear.services.KagamiWearApiService$* { *; }

# Keep services
-keep class com.kagami.wear.tiles.KagamiTileService { *; }
-keep class com.kagami.wear.complications.KagamiComplicationService { *; }
-keep class com.kagami.wear.services.WearDataLayerService { *; }

# Keep Hilt
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }
-keepclasseswithmembernames class * {
    @dagger.hilt.* <methods>;
}
