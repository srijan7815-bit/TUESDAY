# TUESDAY Project Rules

## Architecture
1. Keep a provider abstraction. TUESDAY business logic must use `SandboxProvider`/`WorkspaceManager`, not provider-specific calls scattered through routes, chat, clients, or tools.
2. Use conversation-scoped workspaces. Conversation A must never automatically see or control Conversation B’s filesystem, processes, browser, or desktop.
3. Prefer lazy workspace creation. A conversation gets a workspace only when computer/workspace work is requested.
4. Reuse the same workspace for later turns in the same conversation.
5. Stop or hibernate idle workspaces without destroying persistent user artifacts.
6. Persist workspace metadata in a dedicated database table; do not stuff lifecycle state into the conversation row.
7. Use stable public DTOs. Never return raw Cua/E2B/AIO SDK objects.
8. Keep clients thin. Android and Tauri must call the backend; they must never hold sandbox credentials or control sandboxes directly.

## Security
1. All NVIDIA, E2B, Cua, Fish Audio, Render, storage, and provider keys stay server-side.
2. Never commit `.env`, keys, tokens, credentials, host SSH keys, browser profiles, Docker socket, `/`, `~`, or arbitrary host mounts.
3. Never expose credentials to the model, frontend JavaScript, APK, Linux binary, logs, error details, or conversation history.
4. Normalize and validate paths. Block traversal, absolute host paths, symlink escapes, and access outside the workspace root.
5. Commands execute inside the selected sandbox only. Never use host `subprocess` for agent computer commands.
6. Enforce command timeouts, runtime limits, output limits, file-size limits, upload limits, and concurrency limits.
7. Network access must have a policy boundary. Block localhost, RFC1918/internal ranges, cloud metadata endpoints, and sensitive infrastructure unless explicitly allowed.
8. Destructive, network, local-system, microphone, camera, screen, account, deletion, and external-contact actions require per-action or scoped approval.
9. Local-system access must be opt-in and must show the user what capability is being granted.
10. Provide kill switches for local access, proactive notifications, microphone, camera, and remote computer control.

## Agent/tool rules
1. Use typed JSON-schema tools.
2. Resolve the active conversation workspace server-side; the model must not submit an arbitrary sandbox ID.
3. Support iterative tool-call loops: plan → tool call → result → inspect → next call → verify → artifact export.
4. Attachments go to `/workspace/uploads/`; generated artifacts go to `/workspace/artifacts/`.
5. Tool results must be bounded and understandable.
6. Ask for approval before consequential operations.
7. Provide a safe `WORKSPACE_UNAVAILABLE` path so ordinary chat remains functional.
8. Implement browser helpers only when the provider does not already expose the required capability.

## UI rules
1. Product name is TUESDAY everywhere.
2. Do not redesign away from the supplied HUD references.
3. Use original implementation: blue-black background, cyan/white glow, thin angular borders, glass panels, status cards, notification windows, sci-fi typography.
4. The exact font is pending user-provided `.ttf`, `.otf`, or `.woff2`. Keep font loading replaceable.
5. Use embedded/local assets or data URIs for preview; do not rely on external CDN fonts for the in-app workspace preview.
6. Support responsive Android and lightweight Linux layouts.
7. Show a clear workspace indicator: stopped, starting, running, unavailable.
8. When computer access begins, show a live-screen/screenshot window. A refreshable screenshot is acceptable before full streaming.
9. Include accessible focus states, reduced motion, high contrast, and keyboard navigation.

## Runtime/model rules
1. Use Nemotron 3 Ultra for hard coding/planning when available; if unavailable, use an explicitly disclosed fallback.
2. Never claim a model was used unless an actual successful API call occurred.
3. Runtime routing may select smaller/faster models for latency, but hard coding/engineering remains Ultra-preferred.
4. Whisper is speech recognition, not TTS. Keep STT and TTS providers separate.
5. Fish Audio 2.1 Pro is the requested TTS direction; key/voice/model remain placeholders until configured.
6. Do not send provider secrets in model prompts.

## Testing rules
1. Run syntax/type/lint/unit/integration/build checks where available.
2. Required workspace tests: isolation, reuse, stop/resume, command execution, file operations, screenshot capability, path traversal rejection, unauthorized access rejection, provider failure fallback, concurrent creation, secret non-disclosure, cleanup, artifact transfer.
3. Mock provider tests must be separate from real-provider tests.
4. Do not claim real E2B/Cua execution passed unless it actually ran with configured credentials.
5. Test APK installation and Linux package startup on clean environments before calling release ready.
6. Include checksums and reproducible build metadata for release artifacts.
