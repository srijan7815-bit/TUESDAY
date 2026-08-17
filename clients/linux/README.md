# TUESDAY for Linux Lite

This client is a small native launcher packaged as a Debian `.deb`, suitable for Linux Lite and other Ubuntu/Debian desktops. It opens the hosted HUD in Chromium/Chrome/Brave application mode, with Firefox as a fallback. Reusing the security-maintained system browser keeps the installed package under a few kilobytes and avoids bundling a second browser engine.

## Build and install

```bash
./build-deb.sh
sudo apt install ./dist/tuesday-desktop_1.0.0_all.deb
tuesday-desktop --configure https://your-service.onrender.com
tuesday-desktop --healthcheck
tuesday-desktop
```

The first graphical launch also offers a setup dialog when Zenity is installed. The release client accepts HTTPS origins only. It stores the backend origin with user-only permissions under the XDG config directory; credentials remain in the browser's protected HttpOnly cookie store.

## Commands

- `tuesday-desktop` — open the application.
- `tuesday-desktop --configure URL` — validate and save a new server origin.
- `tuesday-desktop --healthcheck` — verify `/health/ready` over TLS.
- `tuesday-desktop --version` — print the client version.

The `.deb` and SHA-256 file are built on every GitHub push and included in tagged releases.
