# TUESDAY PWA

The installable browser client is served directly by the FastAPI service at `/`. It includes the responsive HUD, a versioned offline shell, 192/512 maskable icons, standalone display metadata, authentication, chat cancellation, workspace screenshots, approvals, attachments, push-to-talk, and optional voice playback.

After the Render backend is healthy, open its HTTPS origin in Chrome, Edge, or another compatible browser and choose **Install app** or **Add to Home Screen**. The PWA uses the same server-side session and never contains provider credentials.

Offline mode exposes only the cached application shell. Chat, memory, remote workspace, approvals, voice providers, and artifacts require the backend.
