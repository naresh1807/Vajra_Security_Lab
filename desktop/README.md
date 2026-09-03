# Vajra Security Lab — desktop app

An Electron shell that runs Vajra as a standalone desktop application. It
starts the bundled FastAPI backend on a private loopback port (the backend
also serves the built React UI, so everything is one origin), waits for
`GET /api/health` to go green, then opens a window on it.

All data lives under the OS user-data directory, **not** in the app bundle:

| | |
|---|---|
| Database | `<userData>/vajra.db` (SQLite) |
| Evidence vault | `<userData>/uploads/` |
| Encryption key | `<userData>/.vajra-data.key` (Fernet — back this up) |
| Backend log | `<userData>/backend.log` |

`<userData>` is `%APPDATA%\vajra-security-lab-desktop` on Windows,
`~/Library/Application Support/vajra-security-lab-desktop` on macOS,
`~/.config/vajra-security-lab-desktop` on Linux.

Registration is open in the desktop build — you create your account on
first launch. Recon still routes through ScopeGuard and the project rate
limit exactly as in the server build.

## Run it (development)

Prerequisites: Node 18+, and the backend venv at `../backend/.venv` with
dependencies installed (`cd ../backend && python -m venv .venv &&
.venv\Scripts\python.exe -m pip install -r requirements.txt`), plus a
built frontend (`npm --prefix ../frontend run build`).

```bash
cd desktop
npm install
npm start
```

`npm start` goes through `start.cjs`, which clears `ELECTRON_RUN_AS_NODE`
first — some IDE terminals (VS Code) set it, and it breaks Electron's
`require("electron")`.

## Build an installer

```bash
cd desktop
npm run dist        # runs `npm run build:frontend` first, then electron-builder
```

Output lands in `desktop/out/`. On Windows this is an NSIS installer.

**Bundling note:** `electron-builder` copies `../backend` — including
`backend/.venv` — into the app's resources. That venv contains
platform-specific binaries (cryptography, psycopg, pydantic-core), so an
installer built on Windows x64 runs only on Windows x64. Build on each
target platform, or switch to a PyInstaller-frozen backend for a
cross-platform single binary.
