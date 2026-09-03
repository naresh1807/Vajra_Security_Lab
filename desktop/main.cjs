"use strict";
/**
 * Vajra Security Lab desktop shell.
 *
 * Starts the bundled FastAPI backend on a private loopback port (which also
 * serves the built React UI at `/`, so the app is single-origin), waits for
 * `GET /api/health` to go green, then opens a window on it. All data - the
 * SQLite database, the evidence vault, and the encryption key - lives under
 * the OS user-data directory, so nothing is written into the app bundle.
 */
const { app, BrowserWindow, shell, dialog, Menu } = require("electron");
const { spawn } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");
const net = require("node:net");
const http = require("node:http");

let backend = null;
let mainWindow = null;

function resourcePath(...parts) {
  return app.isPackaged
    ? path.join(process.resourcesPath, ...parts)
    : path.join(__dirname, "..", ...parts);
}

function pythonExecutable() {
  if (process.platform === "win32") {
    return resourcePath("backend", ".venv", "Scripts", "python.exe");
  }
  return resourcePath("backend", ".venv", "bin", "python");
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

function waitForHealth(port, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(
        { host: "127.0.0.1", port, path: "/api/health", timeout: 2500 },
        (res) => {
          res.resume();
          if (res.statusCode === 200) resolve();
          else retry();
        },
      );
      req.on("error", retry);
      req.on("timeout", () => {
        req.destroy();
        retry();
      });
    };
    const retry = () => {
      if (Date.now() > deadline) {
        reject(new Error("The backend did not become healthy within 60 seconds."));
      } else {
        setTimeout(attempt, 500);
      }
    };
    attempt();
  });
}

async function startBackend() {
  const py = pythonExecutable();
  if (!fs.existsSync(py)) {
    throw new Error(
      `Bundled Python runtime not found at:\n${py}\n\n` +
        "In development, create it with:\n" +
        "  cd backend && python -m venv .venv && .venv\\Scripts\\python.exe -m pip install -r requirements.txt",
    );
  }

  const port = await findFreePort();
  const userData = app.getPath("userData");
  fs.mkdirSync(path.join(userData, "uploads"), { recursive: true });

  const dbPath = path.join(userData, "vajra.db").replace(/\\/g, "/");
  const env = {
    ...process.env,
    VAJRA_STATIC_DIR: resourcePath("frontend", "dist"),
    VAJRA_DATABASE_URL: `sqlite:///${dbPath}`,
    VAJRA_UPLOAD_DIR: path.join(userData, "uploads"),
    VAJRA_DATA_ENCRYPTION_KEY_FILE: path.join(userData, ".vajra-data.key"),
    VAJRA_ALLOW_REGISTRATION: "true", // local single-user: you register on first run
    VAJRA_SECURE_COOKIES: "false", // plain-http loopback
    VAJRA_JOB_QUEUE_BACKEND: "inline",
    PYTHONUNBUFFERED: "1",
    PYTHONDONTWRITEBYTECODE: "1",
  };

  const logPath = path.join(userData, "backend.log");
  const logStream = fs.createWriteStream(logPath, { flags: "a" });
  logStream.write(`\n=== ${new Date().toISOString()} starting backend on :${port} ===\n`);

  backend = spawn(
    py,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port), "--log-level", "info"],
    { cwd: resourcePath("backend"), env, windowsHide: true },
  );
  backend.stdout.pipe(logStream);
  backend.stderr.pipe(logStream);
  backend.on("exit", (code) => {
    backend = null;
    if (code && !app.isQuitting) {
      dialog.showErrorBox(
        "Vajra Security Lab",
        `The backend stopped unexpectedly (exit ${code}).\nLog: ${logPath}`,
      );
      app.quit();
    }
  });

  await waitForHealth(port);
  return port;
}

function stopBackend() {
  if (!backend) return;
  const { pid } = backend;
  backend = null;
  try {
    if (process.platform === "win32") {
      spawn("taskkill", ["/pid", String(pid), "/T", "/F"], { windowsHide: true });
    } else {
      process.kill(pid, "SIGTERM");
    }
  } catch {
    /* already gone */
  }
}

app.on("before-quit", () => {
  app.isQuitting = true;
  stopBackend();
});
app.on("window-all-closed", () => {
  stopBackend();
  app.quit();
});

app.whenReady().then(async () => {
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      { role: "fileMenu" },
      { role: "editMenu" },
      { role: "viewMenu" },
      { role: "windowMenu" },
    ]),
  );

  try {
    const port = await startBackend();
    mainWindow = new BrowserWindow({
      width: 1440,
      height: 900,
      minWidth: 1024,
      minHeight: 680,
      title: "Vajra Security Lab",
      backgroundColor: "#0b0b12",
      autoHideMenuBar: true,
      webPreferences: { contextIsolation: true, nodeIntegration: false },
    });
    // External links open in the system browser, not inside the app.
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
      if (url.startsWith("http")) shell.openExternal(url);
      return { action: "deny" };
    });
    await mainWindow.loadURL(`http://127.0.0.1:${port}/`);
  } catch (err) {
    dialog.showErrorBox("Vajra Security Lab - failed to start", err.stack || String(err));
    app.quit();
  }
});
