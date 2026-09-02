const { app, BrowserWindow, Menu, dialog, globalShortcut, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const net = require("net");
const path = require("path");

const projectRoot = path.resolve(__dirname, "..");
const distRoot = path.join(projectRoot, "frontend", "dist");
const pythonExe = path.join(projectRoot, ".venv", "Scripts", "python.exe");
const packagedBackend = path.join(process.resourcesPath, "backend", "CrimsonAtlasService", "CrimsonAtlasService.exe");
const localUrl = "http://127.0.0.1:7891/";
const stateDir = path.join(process.env.LOCALAPPDATA || projectRoot, "CrimsonAtlas");
const windowStatePath = path.join(stateDir, "window-state.json");
const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".png": "image/png",
  ".jpg": "image/jpeg",
};

app.setName("Crimson Atlas");
app.setPath("userData", path.join(process.env.LOCALAPPDATA || projectRoot, "CrimsonAtlas", "ElectronProfile"));
if (process.platform === "win32") app.setAppUserModelId("CrimsonAtlas.LocalMap");

let mainWindow = null;
let backend = null;
let frontendServer = null;
let shuttingDown = false;
let topmostTimer = null;
let saveWindowTimer = null;

function loadWindowState() {
  try {
    const state = JSON.parse(fs.readFileSync(windowStatePath, "utf8"));
    if (Number.isFinite(state.width) && Number.isFinite(state.height)) return state;
  } catch {}
  return { width: 900, height: 600 };
}

function saveWindowState() {
  if (!mainWindow || mainWindow.isDestroyed() || mainWindow.isMinimized() || mainWindow.isMaximized()) return;
  fs.mkdirSync(stateDir, { recursive: true });
  fs.writeFileSync(windowStatePath, JSON.stringify(mainWindow.getBounds(), null, 2));
}

function scheduleWindowStateSave() {
  if (!mainWindow || mainWindow.isDestroyed() || mainWindow.isMinimized() || mainWindow.isMaximized()) return;
  if (saveWindowTimer) clearTimeout(saveWindowTimer);
  saveWindowTimer = setTimeout(saveWindowState, 250);
}

function serveFrontend() {
  return new Promise((resolve, reject) => {
    frontendServer = http.createServer((request, response) => {
      let requestPath;
      try {
        requestPath = decodeURIComponent((request.url || "/").split("?")[0]);
      } catch {
        response.writeHead(400).end("Bad request");
        return;
      }
      if (requestPath === "/") requestPath = "/index.html";
      const filePath = path.resolve(distRoot, `.${requestPath}`);
      if (!filePath.startsWith(`${path.resolve(distRoot)}${path.sep}`)) {
        response.writeHead(403).end("Forbidden");
        return;
      }
      fs.readFile(filePath, (error, data) => {
        if (error) {
          response.writeHead(404).end("Not found");
          return;
        }
        response.writeHead(200, {
          "Content-Type": mimeTypes[path.extname(filePath).toLowerCase()] || "application/octet-stream",
          "Cache-Control": requestPath === "/index.html" ? "no-store" : "public, max-age=3600",
        });
        response.end(data);
      });
    });
    frontendServer.once("error", reject);
    frontendServer.listen(7891, "127.0.0.1", resolve);
  });
}

function waitForPort(port, timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;
    const attempt = () => {
      if (backend && backend.exitCode !== null) {
        reject(new Error(`Игровая служба завершилась с кодом ${backend.exitCode}`));
        return;
      }
      const socket = net.createConnection({ host: "127.0.0.1", port });
      socket.setTimeout(300);
      socket.once("connect", () => { socket.destroy(); resolve(); });
      const retry = () => {
        socket.destroy();
        if (Date.now() >= deadline) reject(new Error(`Игровая служба не открыла порт ${port}`));
        else setTimeout(attempt, 120);
      };
      socket.once("error", retry);
      socket.once("timeout", retry);
    };
    attempt();
  });
}

function startBackend() {
  const executable = app.isPackaged ? packagedBackend : pythonExe;
  const args = app.isPackaged ? [] : ["-m", "app.main"];
  if (!fs.existsSync(executable)) {
    throw new Error(app.isPackaged
      ? "Не найдена встроенная служба Crimson Atlas. Переустановите приложение."
      : "Не найдено окружение .venv. Запустите Setup Crimson Atlas.bat");
  }
  fs.mkdirSync(stateDir, { recursive: true });
  backend = spawn(executable, args, {
    cwd: app.isPackaged ? stateDir : projectRoot,
    windowsHide: true,
    stdio: ["pipe", "ignore", "pipe"],
    env: { ...process.env, CRIMSON_ATLAS_LOG_DIR: stateDir },
  });
  const log = fs.createWriteStream(path.join(stateDir, "backend.log"), { flags: "a" });
  backend.stderr.pipe(log);
  backend.once("exit", () => log.end());
}

async function createWindow() {
  await serveFrontend();
  startBackend();
  await waitForPort(7892);

  Menu.setApplicationMenu(null);
  const savedWindow = loadWindowState();
  mainWindow = new BrowserWindow({
    title: "Crimson Atlas",
    width: savedWindow.width,
    height: savedWindow.height,
    ...(Number.isFinite(savedWindow.x) && Number.isFinite(savedWindow.y)
      ? { x: savedWindow.x, y: savedWindow.y }
      : {}),
    resizable: true,
    alwaysOnTop: true,
    focusable: true,
    skipTaskbar: false,
    autoHideMenuBar: true,
    backgroundColor: "#0d1012",
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  const openExternalIfAllowed = (url) => {
    try {
      const target = new URL(url);
      if (target.protocol === "https:" && ["ko-fi.com", "crimsondesert.th.gl"].includes(target.hostname)) {
        void shell.openExternal(target.toString());
        return true;
      }
    } catch {}
    return false;
  };
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    openExternalIfAllowed(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (url === localUrl || url.startsWith(localUrl)) return;
    event.preventDefault();
    openExternalIfAllowed(url);
  });
  const reinforceTopmost = () => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    mainWindow.setAlwaysOnTop(true, "screen-saver");
    mainWindow.moveTop();
  };
  reinforceTopmost();
  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  mainWindow.setFullScreenable(false);
  mainWindow.on("show", reinforceTopmost);
  mainWindow.on("focus", reinforceTopmost);
  mainWindow.on("resize", scheduleWindowStateSave);
  mainWindow.on("move", scheduleWindowStateSave);
  mainWindow.on("close", saveWindowState);
  mainWindow.on("blur", () => {
    setTimeout(reinforceTopmost, 50);
    setTimeout(reinforceTopmost, 300);
  });
  topmostTimer = setInterval(reinforceTopmost, 1000);
  globalShortcut.register("CommandOrControl+Shift+A", () => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    reinforceTopmost();
    mainWindow.focus();
  });
  mainWindow.once("ready-to-show", () => mainWindow.show());
  await mainWindow.loadURL(localUrl);
  mainWindow.on("closed", () => {
    if (topmostTimer) clearInterval(topmostTimer);
    if (saveWindowTimer) clearTimeout(saveWindowTimer);
    topmostTimer = null;
    saveWindowTimer = null;
    mainWindow = null;
    app.quit();
  });
}

function stopServices() {
  if (shuttingDown) return;
  shuttingDown = true;
  globalShortcut.unregisterAll();
  if (frontendServer) frontendServer.close();
  if (backend && backend.exitCode === null) {
    backend.stdin.write("shutdown\n");
    backend.stdin.end();
    const forceKill = setTimeout(() => {
      if (backend && backend.exitCode === null) backend.kill();
    }, 5000);
    forceKill.unref();
  }
}

const releaseSmokeTest = process.argv.includes("--release-smoke-test");
const singleInstance = releaseSmokeTest || app.requestSingleInstanceLock();
if (!singleInstance) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });
  app.whenReady().then(async () => {
    if (releaseSmokeTest) {
      const required = [
        path.join(distRoot, "index.html"),
        ...(app.isPackaged ? [packagedBackend] : [pythonExe]),
      ];
      const missing = required.filter((item) => !fs.existsSync(item));
      if (missing.length) throw new Error(`Не найдены файлы релиза: ${missing.join(", ")}`);
      console.log("Crimson Atlas release smoke test passed");
      app.quit();
      return;
    }
    await createWindow();
  }).catch((error) => {
    stopServices();
    dialog.showErrorBox("Crimson Atlas", error.message || String(error));
    app.quit();
  });
  app.on("before-quit", stopServices);
  app.on("window-all-closed", () => app.quit());
}
