"use strict";
/**
 * Dev launcher for the Electron shell.
 *
 * Some IDE-integrated terminals (VS Code, and anything embedding an Electron
 * runtime) export ELECTRON_RUN_AS_NODE=1, which makes `require("electron")`
 * inside the app return a path string instead of the API - the app then
 * crashes on `app.on(...)`. Clearing it here and spawning a fresh Electron
 * process fixes `npm start` regardless of where it's run from.
 */
delete process.env.ELECTRON_RUN_AS_NODE;

const { spawn } = require("node:child_process");
const electronBinary = require("electron"); // path string when run under plain node

const child = spawn(electronBinary, ["."], { stdio: "inherit", env: process.env });
child.on("exit", (code) => process.exit(code ?? 0));
