# Kagami XR ProGuard Rules
#
# Colony: Nexus (e4) - Integration
#
# h(x) >= 0. Always.

# ==============================================================================
# AndroidX XR SDK Rules
# ==============================================================================
# Keep XR runtime classes
-keep class androidx.xr.** { *; }
-keep class com.android.extensions.xr.** { *; }

# Keep XR Compose classes
-keep class androidx.xr.compose.** { *; }

# Keep ARCore classes
-keep class com.google.ar.** { *; }
-keep class androidx.xr.arcore.** { *; }

# ==============================================================================
# Kotlin Coroutines
# ==============================================================================
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}
-keepclassmembers class kotlinx.coroutines.** {
    volatile <fields>;
}
-keepclassmembernames class kotlinx.** {
    volatile <fields>;
}

# ==============================================================================
# Kotlin Serialization
# ==============================================================================
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt
-keepclassmembers @kotlinx.serialization.Serializable class ** {
    *** Companion;
    *** INSTANCE;
    kotlinx.serialization.KSerializer serializer(...);
}
-if @kotlinx.serialization.Serializable class **
-keepclassmembers class <1>$Companion {
    kotlinx.serialization.KSerializer serializer(...);
}

# ==============================================================================
# Hilt / Dagger
# ==============================================================================
-keepclasseswithmembers class * {
    @dagger.* <methods>;
}
-keep class dagger.* { *; }
-keep class javax.inject.* { *; }
-keep class * extends dagger.hilt.android.internal.managers.ComponentSupplier

# ==============================================================================
# Retrofit / OkHttp
# ==============================================================================
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn retrofit2.**
-keep class retrofit2.** { *; }
-keepclasseswithmembers class * {
    @retrofit2.http.* <methods>;
}

# ==============================================================================
# Moshi
# ==============================================================================
-keep class com.squareup.moshi.** { *; }
-keepclassmembers class * {
    @com.squareup.moshi.* <methods>;
}

# ==============================================================================
# Gemini AI
# ==============================================================================
-keep class com.google.ai.client.** { *; }

# ==============================================================================
# Kagami XR App Classes
# ==============================================================================
-keep class com.kagami.xr.** { *; }
-keepclassmembers class com.kagami.xr.** {
    *;
}

# Keep hand tracking gesture classes
-keep enum com.kagami.xr.services.HandTrackingService$Gesture { *; }
-keep enum com.kagami.xr.services.ThermalManager$QualityProfile { *; }

# ==============================================================================
# General Rules
# ==============================================================================
# Preserve line number information for debugging
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# Remove logging in release
-assumenosideeffects class android.util.Log {
    public static *** d(...);
    public static *** v(...);
}
