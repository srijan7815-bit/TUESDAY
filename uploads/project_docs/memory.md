# TUESDAY Memory / Project Context

## Product identity
- Product name: **TUESDAY**.
- It is intended to be a personal, highly agentic AI assistant similar to ChatGPT/Codex.
- The user wants a lightweight Linux app, Android app/APK, and PWA/browser fallback.
- The user wants a futuristic HUD interface based on supplied reference images: blue-black sci-fi panels, thin luminous cyan/white borders, glass/blur surfaces, angular accents, status panels, notification overlays, and floating desktop/system windows.
- The exact font was requested, but the user has not yet supplied the font file. The reference images do not identify the exact font. Keep a font asset placeholder and make it replaceable with `.ttf`, `.otf`, or `.woff2`.

## Core capabilities requested
- Chat with streaming responses.
- Persistent conversation history.
- Explicit memory with inspect, save, forget, export, and disable controls.
- Live voice mode with speech input/output, interruption/barge-in where practical.
- Best available NVIDIA speech models for STT; Whisper Large V3 or Nemotron ASR Streaming were discussed. Whisper is STT, not TTS.
- High-quality TTS, specifically Fish Audio 2.1 Pro was requested later. Keep Fish Audio key/voice/model placeholders in server configuration.
- Image input and attachments.
- Smart model routing that changes models based on task, complexity, context, language, latency, and budget.
- Agentic skills, MCP, tool registry, workspace, artifacts, browser, terminal, Git, Python, Node, and files.
- TUESDAY should be able to use a remote isolated computer workspace per conversation.
- TUESDAY should be able to modify its own system only through controlled, versioned, approval-gated changes; never silently rewrite production or bypass safety.
- Optional proactive contact/notifications, with explicit opt-in, quiet hours, rate limits, categories, and kill switch. No autonomous consequential external messages without approval.
- Live computer window/screen should appear whenever TUESDAY accesses its remote system. A screenshot/refresh panel is acceptable before a full interactive live stream.
- Local-system access must require approval. User selected both per-action approval and scoped approvals.

## Model plan
- Primary hard reasoning/coding model: `nvidia/nemotron-3-ultra-550b-a55b`.
- Fast runtime model can be a smaller Nemotron model when needed, but Ultra is preferred for coding and complex agent work.
- The user initially required Ultra-only coding, then authorized fallback to the agent’s own coding models if Ultra is unavailable.
- NVIDIA API key was pasted in chat and must be treated as compromised; never store or repeat it. User said it would be revoked after the session.

## Current repository state
Workspace root: `/home/user`.
Current important files:
- `PROJECT_PLAN.md`: broad architecture and roadmap.
- `NEMOTRON_REVIEW.md`: Nemotron review correcting unrealistic assumptions and suggesting Phase 1.
- `NEMOTRON_CODEGEN_BACKEND.txt`, `NEMOTRON_CODEGEN_UI.txt`, `NEMOTRON_CODEGEN_CUA.txt`: model-generation scratch outputs; do not treat as authoritative source files.
- `.env.example`: server-side configuration placeholders.
- `README.md`: initial API and workspace notes.
- `services/api/app/main.py`: FastAPI app, health endpoint, streaming chat endpoint, static UI, workspace router.
- `services/api/app/core/config.py`: Pydantic settings for NVIDIA and sandbox config.
- `services/api/app/core/model_adapter.py`: OpenAI-compatible NVIDIA streaming adapter.
- `services/api/app/static/index.html`: current single-file TUESDAY UI with dark glass style and streaming chat client.
- `services/api/app/static/app.js` and `styles.css`: generated UI files exist, though the active index is currently self-contained.
- `services/api/app/sandbox/provider.py`: provider protocol and DTOs.
- `services/api/app/sandbox/manager.py`: conversation-keyed in-memory manager with locks/ownership.
- `services/api/app/sandbox/cua_provider.py`: optional Cua provider; safe unavailable path.
- `services/api/app/sandbox/e2b_provider.py`: initial E2B cloud provider adapter.
- `services/api/app/routes/workspaces.py`: workspace status/start/stop/execute/screenshot routes.
- `services/api/tests/test_workspaces.py`: generated test file exists but must be inspected/fixed/expanded.

Python compilation has passed for the current backend at least once with `python -m compileall -q services/api/app`.

## Existing integration details
- Current chat endpoint: `POST /v1/chat/stream` with `{messages:[{role,content}], model?, temperature?, max_tokens?}`.
- Root UI endpoint: `/`.
- Workspace routes:
  - `GET /v1/conversations/{conversation_id}/workspace`
  - `POST /v1/conversations/{conversation_id}/workspace/start`
  - `POST /v1/conversations/{conversation_id}/workspace/stop`
  - `POST /v1/conversations/{conversation_id}/workspace/execute`
  - `GET /v1/conversations/{conversation_id}/workspace/screenshot`
- Default provider was changed to E2B via `SANDBOX_PROVIDER=e2b`; Cua remains optional.
- `.env.example` includes placeholders for NVIDIA, E2B, Cua, idle timeout, image, and runtime limits.
- Do not assume the current E2B SDK signatures are correct; inspect the installed SDK/docs before real integration.

## Sandbox decisions
- Cua cloud requires early access for the user, so it is not currently usable as the primary remote provider.
- `pip install cua` installed Cua/Lume host tooling but importing `cua` initially failed due to environment/path confusion. Do not assume it is the cloud Sandbox SDK.
- AIO Sandbox (`https://sandbox.agent-infra.com/`) was considered as a self-hosted Docker alternative, not genuinely cloud-free. It offers browser, shell, files, VS Code, Jupyter, and MCP through one container.
- E2B was selected as the best non-local free starting point: official Hobby tier has one-time free credits, no credit card requirement according to current E2B pricing, cloud Firecracker sandboxes, and documented desktop/XFCE computer use.
- E2B official computer-use docs show desktop screenshots, clicks, typing, scrolling, keypresses, and terminal commands. E2B has an Ubuntu/XFCE desktop template with Xorg/Xvfb, x11vnc, and noVNC.
- E2B requires a server-side `E2B_API_KEY` and possibly a template ID for a custom desktop image.

## User-provided references
Attachments are in `/home/user/uploads/`:
- `which-system-interface-do-you-prefer-the-black-gold-ui-goes-v0-nnkgo86kzome1.webp`
- `original-47b0a800629ab9552e7a5c50f0930470.webp`
- `images.jpeg`
- `582bed209213453.Y3JvcCw5ODEsNzY4LDE5Miww.png`
These show the desired sci-fi HUD/status/notification look and an XFCE/Linux desktop reference.
