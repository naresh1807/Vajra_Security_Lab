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

Output in `desktop/out/`:

| File | What |
|---|---|
| `Vajra-Security-Lab-<ver>-exe.exe` | NSIS installer (~100 MB) |
| `Vajra-Security-Lab-<ver>-zip.zip` | portable — unzip and run `Vajra Security Lab.exe` (~130 MB) |
| `win-unpacked/` | the unpacked app directory |

**winCodeSign on Windows without admin:** electron-builder unpacks a
`winCodeSign` tool archive that contains macOS symlinks; creating those
needs a privilege a normal Windows account lacks, and the build aborts.
Work around it once by pre-extracting the archive without the `darwin`
folder:

```powershell
$c = "$env:LOCALAPPDATA\electron-builder\Cache\winCodeSign"
& "node_modules\7zip-bin\win\x64\7za.exe" x "$c\<downloaded>.7z" -o"$c\winCodeSign-2.6.0" -y "-xr!darwin"
```

(The app isn't code-signed either way — there's no certificate — so
Windows SmartScreen will warn on first run.)

**Cross-platform:** `electron-builder` copies `../backend` including
`backend/.venv`, whose native extensions (cryptography, psycopg,
pydantic-core) are platform-specific. An installer built on Windows x64
runs only on Windows x64 — build on each target OS, or freeze the backend
with PyInstaller for a portable single binary.
