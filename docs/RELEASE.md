# Client and release guide

## Android debug build

The Android app targets API 36, supports API 26+, and builds with JDK 17, Android Gradle Plugin 8.13.2, and Gradle 8.13.

```bash
cd clients/android
./gradlew testDebugUnitTest lintDebug assembleDebug
```

The bootstrap script downloads the official Gradle 8.13 binary and verifies its SHA-256 before execution. A debug APK is also uploaded by every successful GitHub CI run.

## Android signed release

Create and protect a release keystore outside the repository. Add these encrypted GitHub Actions secrets:

- `TUESDAY_ANDROID_KEYSTORE_BASE64`
- `TUESDAY_ANDROID_KEYSTORE_PASSWORD`
- `TUESDAY_ANDROID_KEY_ALIAS`
- `TUESDAY_ANDROID_KEY_PASSWORD`

The first value is the base64 representation of the keystore file. Never commit the keystore or put it in a workflow artifact. Push a semantic version tag only after CI succeeds:

```bash
git tag -s v1.0.0 -m "TUESDAY 1.0.0"
git push origin v1.0.0
```

The release workflow tests and lints Android, requires all signing secrets, creates a signed minimized APK, builds the Linux package, emits SHA-256 files, and attaches the results to a GitHub release. Keep the keystore and passwords backed up securely; Android updates must use the same signing identity.

## Linux Lite

```bash
cd clients/linux
./build-deb.sh
sudo apt install ./dist/tuesday-desktop_1.0.0_all.deb
tuesday-desktop --configure https://your-service.onrender.com
```

GitHub releases contain the same `.deb` and checksum. Verify it before installation:

```bash
cd clients/linux/dist
sha256sum --check tuesday-desktop_1.0.0_all.deb.sha256
```

## Version updates

Before tagging, update the Android `versionCode`/`versionName`, Linux `APP_VERSION`, release notes, and tests. A higher Android `versionCode` is mandatory for every store or in-place upgrade.

Android requirements reference: [Google Play target API requirements](https://developer.android.com/google/play/requirements/target-sdk) and [Android Gradle Plugin compatibility](https://developer.android.com/build/releases/gradle-plugin).
