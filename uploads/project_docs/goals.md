# TUESDAY Final Goals

## Product
Build TUESDAY as a production-quality, lightweight personal AI assistant for Android, Linux, and PWA/browser fallback. It should feel like an agentic ChatGPT/Codex-style system with memory, tools, workspace, voice, images, and a polished HUD interface.

## Clients
- Android APK built from the shared client architecture.
- Lightweight Linux executable/AppImage, preferably Tauri rather than Electron.
- PWA fallback where practical.
- Clients are thin: backend owns provider credentials, workspace lifecycle, model routing, memory, and agent execution.

## Chat and models
- NVIDIA Nemotron 3 Ultra is the preferred primary model for hard reasoning, coding, planning, debugging, and agent workflows.
- Smart runtime routing changes models based on task type, complexity, context, latency, language, health, and budget.
- Streaming responses, cancellation, retries, circuit breakers, token budgets, and understandable errors.
- Preserve normal chat when optional computer infrastructure is unavailable.

## Memory
- Conversation history.
- Explicit profile/preferences memory.
- Episodic summaries with retention controls.
- Semantic/document memory when embeddings are available.
- User controls: remember, forget, inspect, disable, export, delete all.
- Memory must respect privacy and never send disabled/deleted memory to a model.

## Computer/workspace system
Each conversation gets a private remote computer only when needed:

```text
Conversation
  → Agent
    → WorkspaceManager
      → SandboxProvider
        → E2B cloud desktop sandbox
```

The default remote provider should be E2B because it is cloud-hosted, free to start, supports Firecracker isolation, and documents full Ubuntu/XFCE computer use. Keep provider adapters for AIO Sandbox and Cua where useful.

Required workspace capabilities:
- Create/reuse/start/stop/restart/delete/snapshot/restore where provider supports them.
- Conversation-scoped isolated state.
- Persistent files across turns.
- `/workspace/uploads`, `/workspace/artifacts`, `/workspace/projects`, `/workspace/scratch`, `/workspace/home`.
- Read/write/edit/list/mkdir/move/delete files.
- Run shell, Python, Node, Git, builds, tests, and permitted package installs.
- Clone repositories.
- Browser and GUI interaction.
- Screenshots, mouse, keyboard, scrolling, keypress.
- Attachment staging and artifact export.
- Idle shutdown/hibernate and safe restore.
- Live screenshot/desktop panel shown when the agent uses the remote system.

## Agent tools
Add typed tools such as:
- `computer_read_file`
- `computer_write_file`
- `computer_list_dir`
- `computer_mkdir`
- `computer_move_file`
- `computer_delete_file`
- `computer_run_command`
- `computer_screenshot`
- `computer_click`
- `computer_double_click`
- `computer_scroll`
- `computer_type`
- `computer_keypress`
- `computer_get_screen_size`
- `computer_upload_attachment`
- `computer_export_artifact`

Tools must resolve the active conversation workspace server-side and participate in a multi-step tool loop.

## Voice and media
- Voice input with best available NVIDIA STT, including Whisper Large V3 or Nemotron ASR Streaming depending on language/latency.
- Natural voice output using Fish Audio 2.1 Pro if configured, with a safe fallback.
- Push-to-talk and hands-free live mode.
- VAD, interruption/barge-in, partial transcripts, stream cancellation.
- Image input and attachment handling.
- Audio is not stored by default; recording requires opt-in.

## Local-system access
TUESDAY may access the user’s local system only after explicit approval:
- Per-action approvals by default.
- Optional scoped approvals for selected folders/capabilities and limited duration.
- Visible permission dialog/window.
- No host-wide access by default.
- No root, SSH keys, Docker socket, browser profile, `.env`, or secret mounts.
- Clear audit trail and kill switch.

## UI direction
Recreate the supplied reference language with original assets/code:
- Sci-fi HUD status interface.
- Blue-black glass background.
- Thin white/cyan borders and glows.
- Angular brackets/corner decorations.
- Status cards, resource bars, notifications, and system overlays.
- Floating XFCE-like remote computer window for live E2B desktop.
- Theme controls, motion reduction, accessibility, and responsive layouts.
- Exact custom font should be embedded when the user supplies the font file.

## Proactive behavior
- Optional proactive notifications/contact on explicit opt-in only.
- Quiet hours, notification categories, rate limits, daily budget, and kill switch.
- TUESDAY may notify about completed tasks, failures, approvals, scheduled reminders, or requested follow-ups.
- No autonomous consequential external communication without confirmation.

## Backend/deployment
- FastAPI backend with SSE/WebSocket streaming.
- SQLAlchemy/PostgreSQL with migrations; SQLite may be used for development.
- Dedicated workspace table and repository.
- File/object storage for attachments and artifacts.
- Secure auth, rate limits, HTTPS, structured logs, redaction, health checks, retries, and observability.
- Render-ready deployment configuration with all secrets supplied through environment variables.
- Docker Compose development setup without giving AI-controlled code unrestricted Docker-host access.

## Production acceptance
TUESDAY is ready only when:
1. Android APK installs and passes chat, memory, voice, image, workspace, and approval smoke tests.
2. Linux executable/AppImage launches on a clean supported Linux system.
3. E2B cloud sandbox is actually created and tested with real credentials.
4. Two conversations receive separate sandboxes and cannot see each other’s files.
5. Files survive stop/resume according to the provider strategy.
6. A Python project can be created, run, debugged, tested, and exported autonomously through approved tools.
7. Live screenshot/desktop visibility works when computer tools are used.
8. Secrets do not appear in source, clients, logs, model context, responses, or artifacts.
9. Tool permissions, path validation, timeouts, network policy, and cleanup tests pass.
10. Render deployment succeeds from a clean checkout.
11. Documentation covers setup, secrets, deployment, provider limitations, troubleshooting, and rollback.
12. Release artifacts include versioning, checksums, and exact test results.
