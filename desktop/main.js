"use strict";

const { app, BrowserWindow, shell, dialog } = require("electron");
const { APP_HOME, isTrustedUrl } = require("./security");

// No Node integration, preload scripts, remote module, or arbitrary navigation.
function createWindow() {
  const window = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 840,
    minHeight: 600,
    title: "Nexus School Desktop",
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    },
  });

  window.webContents.setWindowOpenHandler(({ url }) => {
    if (isTrustedUrl(url)) {
      void shell.openExternal(url);
    }
    return { action: "deny" };
  });

  window.webContents.on("will-navigate", (event, url) => {
    if (!isTrustedUrl(url)) event.preventDefault();
  });

  window.webContents.on("will-redirect", (event, url) => {
    if (!isTrustedUrl(url)) event.preventDefault();
  });

  window.once("ready-to-show", () => window.show());
  window.loadURL(APP_HOME).catch(() => {
    void dialog.showMessageBox(window, {
      type: "warning",
      title: "Connection unavailable",
      message: "Nexus School requires an internet connection. Please reconnect and restart the app.",
    });
    window.show();
  });
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
