# Nexus School Mobile — connected client foundation

Android APK and iOS clients share Django's school accounts and data. This first
Expo screen is a secure WebView-based connected client, **not yet a full native
feature rewrite**. It intentionally does not persist school data for offline use.

## Develop

```sh
cd mobile
npm install
npm test
npm run typecheck
npm start
```

## Internal Android APK

The `preview` EAS profile requests an APK (`android.buildType = apk`). After
creating an Expo project and configuring its own approved Expo build credentials,
run `npx eas-cli build --platform android --profile preview`. Do not reuse
credentials from an unrelated repository. Test the downloaded APK on physical
Android devices before exposing a public download link.

The app uses the same `https://learningmanagementsystem.pythonanywhere.com`
site as the desktop client. Configure native deep links, accessibility, native
notifications and token-based API authentication before replacing WebView
journeys with fully native screens.
