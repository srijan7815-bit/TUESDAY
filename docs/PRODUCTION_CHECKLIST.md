# Production acceptance checklist

Record the date, deployed commit SHA, service URL, Android version, Linux package version, and tester for every run. Do not mark an integration as passing based only on a health flag.

## Automated gates

- [ ] GitHub backend job: lint, format, type check, all tests, migrations, credential scan.
- [ ] GitHub web job: all browser scripts parse.
- [ ] GitHub Android job: unit tests, lint, and APK build.
- [ ] GitHub Linux job: shell validation, `.deb` build, and package inspection.
- [ ] Render `/health/live` and `/health/ready` return HTTP 200.
- [ ] Render deploy references the same commit SHA that passed CI.

## Authentication and browser

- [ ] Unauthenticated `/v1/memory` returns 401.
- [ ] A wrong owner token is rejected and the correct token creates a secure session.
- [ ] Login, logout, reload, and session expiry behave correctly.
- [ ] Chat streams, reconnects after a temporary network interruption, and preserves conversation context.
- [ ] PWA installs on a supported browser and opens in standalone mode.
- [ ] Responsive HUD is usable with keyboard, touch, reduced motion, and narrow screens.

## Live model and workspace

- [ ] Health reports `mock_model=false`, `sandbox_provider=e2b`, and `e2b_configured=true`.
- [ ] NVIDIA returns a real streamed response and the UI identifies the configured model.
- [ ] A new conversation lazily starts exactly one E2B desktop.
- [ ] Shell, file write/read/list/move/delete, screenshot, click, double-click, scroll, type, and keypress work in that desktop.
- [ ] Two conversations cannot see each other's files or provider handles.
- [ ] Workspace unavailable/error states do not take chat down.
- [ ] Idle timeout pauses the workspace and a later action resumes it with files intact.
- [ ] Concurrent workspace cap produces a clear error rather than overspending.

## Approval and data safety

- [ ] Shell, delete, and GUI input each create a clear pending approval.
- [ ] Denial blocks the action.
- [ ] Approval permits exactly one matching action; a changed or repeated action asks again.
- [ ] Traversal, host paths, oversized requests/files/audio, and unsupported attachment types are rejected.
- [ ] Memory remember, disable, export, forget, and delete-all work as labeled.
- [ ] Logs do not contain access tokens, provider keys, cookies, private conversation text, or file contents.

## Voice and clients

- [ ] If STT is enabled, Android and browser push-to-talk return an accurate transcript; otherwise UI shows a controlled unavailable message.
- [ ] If Fish Audio is enabled, voice playback works; otherwise UI shows a controlled unavailable message.
- [ ] Signed release APK installs on API 26 and API 36 devices/emulators.
- [ ] Android release rejects HTTP, foreign-origin navigation, and invalid TLS; uploads, microphone, back navigation, and authenticated downloads work.
- [ ] Linux `.deb` installs on the supported Linux Lite release, configures the HTTPS origin, passes `--healthcheck`, launches the HUD, and uninstalls cleanly.

## Recovery

- [ ] PostgreSQL backup/restore procedure has been tested with non-sensitive sample data.
- [ ] Render rollback procedure is documented and tested without reversing a migration blindly.
- [ ] NVIDIA, E2B, Fish, owner token, Android signing, and GitHub secret rotation owners are known.
- [ ] Alerts or routine checks cover readiness failures, provider errors, database capacity, and E2B spending.
