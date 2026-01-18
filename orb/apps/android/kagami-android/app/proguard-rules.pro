# Kagami Android ProGuard Rules
#
# Colony: Nexus (e4) - Integration
# h(x) >= 0 always

# =============================================================================
# GENERAL ANDROID RULES
# =============================================================================

# Keep @Keep annotated classes and members
-keep @androidx.annotation.Keep class * { *; }
-keepclassmembers class * {
    @androidx.annotation.Keep *;
}

# =============================================================================
# HOUSEHOLD MODELS
# =============================================================================

# Keep all model classes for serialization/Parcelable
-keep class com.kagami.android.models.** { *; }
-keepclassmembers class com.kagami.android.models.** { *; }

# Keep enum values (needed for serialization)
-keepclassmembers enum com.kagami.android.models.** {
    <fields>;
    public static **[] values();
    public static ** valueOf(java.lang.String);
}

# =============================================================================
# KOTLIN SERIALIZATION & PARCELIZE
# =============================================================================

# Keep Parcelable creators
-keepclassmembers class * implements android.os.Parcelable {
    public static final android.os.Parcelable$Creator *;
}

# Keep Serializable classes
-keepclassmembers class * implements java.io.Serializable {
    static final long serialVersionUID;
    private static final java.io.ObjectStreamField[] serialPersistentFields;
    private void writeObject(java.io.ObjectOutputStream);
    private void readObject(java.io.ObjectInputStream);
    java.lang.Object writeReplace();
    java.lang.Object readResolve();
}

# =============================================================================
# MOSHI JSON PARSING
# =============================================================================

-keep class com.squareup.moshi.** { *; }
-keepclassmembers class * {
    @com.squareup.moshi.* <methods>;
}

# =============================================================================
# RETROFIT
# =============================================================================

-keepattributes Signature
-keepattributes Exceptions
-keepclassmembers,allowshrinking,allowobfuscation interface * {
    @retrofit2.http.* <methods>;
}
-dontwarn org.codehaus.mojo.animal_sniffer.IgnoreJRERequirement
-dontwarn javax.annotation.**
-dontwarn kotlin.Unit
-dontwarn retrofit2.KotlinExtensions

# =============================================================================
# OKHTTP
# =============================================================================

-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn javax.annotation.**

# =============================================================================
# FIREBASE
# =============================================================================

-keep class com.google.firebase.** { *; }
-keep class com.google.android.gms.** { *; }

# =============================================================================
# HILT DEPENDENCY INJECTION
# =============================================================================

-keep class dagger.** { *; }
-keep class javax.inject.** { *; }
-keep class * extends dagger.hilt.android.internal.managers.ViewComponentManager$FragmentContextWrapper { *; }

# =============================================================================
# COMPOSE
# =============================================================================

# Keep Compose stability annotations
-keep class androidx.compose.runtime.** { *; }

# =============================================================================
# COROUTINES
# =============================================================================

-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}
-keepclassmembers class kotlinx.coroutines.** {
    volatile <fields>;
}
-dontwarn kotlinx.coroutines.**

# =============================================================================
# ROOM DATABASE
# =============================================================================

-keep class * extends androidx.room.RoomDatabase
-keep @androidx.room.Entity class *
-dontwarn androidx.room.paging.**

# =============================================================================
# JNA / UNIFFI BINDINGS (Kagami Mesh SDK)
# =============================================================================

# Keep JNA classes for native library loading
-keep class com.sun.jna.** { *; }
-keepclassmembers class * extends com.sun.jna.Structure {
    <fields>;
    <init>(...);
}
-keepclassmembers class * implements com.sun.jna.Callback {
    <methods>;
}

# Keep UniFFI generated bindings
-keep class uniffi.kagami_mesh_sdk.** { *; }
-keepclassmembers class uniffi.kagami_mesh_sdk.** {
    <fields>;
    <methods>;
}

# Keep UniFFI interfaces and their implementations
-keep interface uniffi.kagami_mesh_sdk.*Interface { *; }
-keep class uniffi.kagami_mesh_sdk.MeshIdentity { *; }
-keep class uniffi.kagami_mesh_sdk.MeshConnection { *; }

# Don't warn about JNA internal classes
-dontwarn com.sun.jna.internal.**

# =============================================================================
# DEBUG INFO
# =============================================================================

# Keep source file names and line numbers for better crash reports
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# 鏡
