plugins {
    id("com.android.application")
}

android {
    namespace = "ai.tuesday.client"
    compileSdk = 36

    defaultConfig {
        applicationId = "ai.tuesday.client"
        minSdk = 26
        targetSdk = 36
        versionCode = 10000
        versionName = "1.0.0"
        testInstrumentationRunner = "android.test.InstrumentationTestRunner"
    }

    val keystorePath = System.getenv("TUESDAY_ANDROID_KEYSTORE_PATH")
    val keystorePassword = System.getenv("TUESDAY_ANDROID_KEYSTORE_PASSWORD")
    val keyAliasValue = System.getenv("TUESDAY_ANDROID_KEY_ALIAS")
    val keyPasswordValue = System.getenv("TUESDAY_ANDROID_KEY_PASSWORD")

    signingConfigs {
        if (!keystorePath.isNullOrBlank() && !keystorePassword.isNullOrBlank()
            && !keyAliasValue.isNullOrBlank() && !keyPasswordValue.isNullOrBlank()) {
            create("release") {
                storeFile = file(keystorePath)
                storePassword = keystorePassword
                keyAlias = keyAliasValue
                keyPassword = keyPasswordValue
                enableV1Signing = true
                enableV2Signing = true
                enableV3Signing = true
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            if (signingConfigs.names.contains("release")) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    lint {
        abortOnError = true
        checkReleaseBuilds = true
        warningsAsErrors = true
        disable += setOf("UnusedResources")
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
