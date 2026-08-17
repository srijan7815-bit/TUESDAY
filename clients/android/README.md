# TUESDAY Android

Thin native Android client for the hosted TUESDAY backend. It targets Android 16 / API 36, supports Android 8+ (API 26), and keeps NVIDIA, E2B, Fish Audio, and Render credentials on the server.

## Build

Use Android Studio with JDK 17, Android SDK 36, and Gradle 8.13, or run:

```bash
./gradlew :app:assembleDebug
```

The repository's GitHub Actions workflow builds and tests this project on every push. A signed release requires the four Android signing secrets documented in `docs/RELEASE.md`.

## First launch

Enter the HTTPS URL of the Render service, such as `https://your-service.onrender.com`. The app then loads the responsive HUD and the server asks for the personal access token. The token becomes a server-signed HttpOnly cookie; it is never compiled into the APK.

## Security

- Cleartext HTTP is blocked in release builds.
- Debug builds allow HTTP only for localhost, `127.0.0.1`, and the emulator host alias `10.0.2.2`.
- Navigation stays on the configured backend origin; other links open in the system browser.
- TLS errors are cancelled, not bypassed.
- JavaScript bridges, file access, content access, mixed content, and WebView debugging are disabled in release.
- Microphone access is requested only for the configured backend origin and only while using push-to-talk.
- File uploads use Android's document picker.
