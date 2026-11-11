# Nexus School Desktop

This Electron client opens the live Django SaaS site in a locked-down window.
School account sessions and database operations still require a connection to
the web server; this client has **no offline access to student records**.

## Local development

```sh
cd desktop
npm install
npm test
npm start
```

## Windows installer

The `Windows desktop installer` GitHub Actions workflow builds an unsigned
Windows `.exe` and uploads it as a workflow artifact. Until signing is set up,
Windows SmartScreen may warn users. Do not advertise it as a trusted or
production-signed download. The installer is not published automatically to
PythonAnywhere; validate it on Windows 10/11 before distribution.

Use `npm run dist:linux` on Linux to prepare an AppImage after testing and
verifying the build toolchain. macOS requires its own build/signing process.

This shell is a **first desktop deliverable**, not a substitute for the
separate Android APK and iOS applications.
