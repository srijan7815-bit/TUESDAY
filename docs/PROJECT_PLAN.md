# TUESDAY Project Plan

## Phase 0 — Bootstrap (this checkout)

- [x] Repository layout
- [x] Specs copied from user uploads
- [x] `.env.example`, README, setup docs

## Phase 1 — Backend core + HUD (current)

- [x] FastAPI app, health, static HUD UI
- [x] Config via pydantic-settings
- [x] Model adapter (NVIDIA OpenAI-compatible + mock)
- [x] SSE streaming chat
- [x] SQLAlchemy models: conversations, messages, memory, workspaces, approvals
- [x] SandboxProvider protocol + DTOs
- [x] Local sandbox provider (isolated temp dirs, path guards)
- [x] E2B provider adapter (optional; safe unavailable path)
- [x] Cua provider stub (unavailable without credentials)
- [x] WorkspaceManager (conversation-scoped, lazy, reuse, stop)
- [x] Workspace HTTP routes
- [x] Agent tool registry + iterative loop
- [x] Memory API (profile / episodic / controls)
- [x] Approval gate stubs
- [x] Unit/integration tests with local provider
- [x] Docker Compose for API (+ optional Postgres)

## Phase 2 — Computer use polish

- [ ] Real E2B desktop template + screenshot streaming panel
- [ ] Full mouse/keyboard tool surface against live desktop
- [ ] Artifact export pipeline
- [ ] Idle hibernate + restore verification on E2B
- [ ] Network policy enforcement inside sandbox

## Phase 3 — Voice & media

- [ ] STT pipeline (Whisper / Nemotron ASR)
- [ ] Fish Audio TTS integration
- [ ] Push-to-talk + hands-free mode in UI
- [ ] Image attachment staging to workspace uploads

## Phase 4 — Clients

- [ ] PWA manifest + offline shell
- [ ] Android thin client (WebView or native chat shell)
- [ ] Tauri Linux app shell
- [ ] Shared API client package

## Phase 5 — Production hardenin

- [ ] Auth (sessions / API tokens)
- [ ] Rate limits, observability, redaction
- [ ] Render deployment
- [ ] Release checksums, APK + AppImage smoke tests
- [ ] Full acceptance checklist from goals.md

## Non-goals (explicit)

- Host subprocess for agent computer commands
- Bundling provider keys into clients
- Silent self-modification of production without approval
