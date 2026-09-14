# Installing the Roti Connect Android app

No Play Store yet — this is a sideloaded APK (`docs/mobile/FLUTTER_APP_PLAN.md`
Phase 5 decision). Read that file for the full project status; this doc is
just the install steps.

## Building the APK

From `mobile/`:

```bash
flutter pub get
flutter build apk --release --split-per-abi
```

Produces three APKs under `mobile/build/app/outputs/flutter-apk/`:

| File | Use |
|---|---|
| `app-arm64-v8a-release.apk` | Almost every phone from the last ~7 years. Install this one unless you know otherwise. |
| `app-armeabi-v7a-release.apk` | Older 32-bit ARM devices. |
| `app-x86_64-release.apk` | Emulators / x86 devices. |

A plain `flutter build apk --release` (no `--split-per-abi`) produces one
universal APK instead — larger (~3x), but installs anywhere without picking
an ABI.

### Signing

`mobile/android/app/key.properties` + `mobile/android/app/roti-connect-upload-keystore.jks`
hold the release signing key, generated 2026-09-14. **Both are gitignored on
purpose — never commit them.** Back the `.jks` file and the passwords in
`key.properties` up somewhere safe (a password manager, encrypted storage):
if this keystore is lost, every future release build gets a *different*
signature, and Android refuses to install an update signed by a different
key over an already-installed one — anyone who installed an earlier build
would have to uninstall it first to get a new one.

If `key.properties` is missing (e.g. a fresh checkout without it), the build
still succeeds but falls back to Flutter's debug signing key
(`android/app/build.gradle.kts` handles this automatically) — fine for
`flutter run --release` on a dev machine, not for anything you hand to a
real user.

## Installing on a device

1. Get the APK onto the phone (email it to yourself, use `adb push`, a
   cloud drive link, whatever's convenient).
2. On the phone: Settings → Apps → look for "install unknown apps" /
   "allow from this source" for whichever app you used to open the APK
   (Files, Gmail, Chrome downloads, ...) and enable it. Android will
   prompt for this automatically the first time you try to open an APK
   if it isn't already allowed.
3. Open the APK file → Install.

## What you're installing

- Talks to the **dev/staging** deploy at `http://204.168.249.99:8105/api/v1/`
  over plain HTTP (no TLS yet — `docs/DOMAIN_AND_SSL.md`, `docs/DEPLOYMENTS.md`).
  `mobile/android/app/src/main/res/xml/network_security_config.xml` carves
  out cleartext HTTP for that one IP only; everything else on the device
  still requires HTTPS as normal.
- Session/basket state: the basket now persists across app restarts
  (`shared_preferences`); the signed-in session does **not** yet (in-memory
  cookie jar only — see `docs/mobile/FLUTTER_APP_PLAN.md` Phase 2/4).
- Known gaps at time of writing: no push notifications (blocked — needs a
  Firebase project, see Phase 4 in the plan doc), no Play Store listing.
