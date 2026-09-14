# Roti Connect — Android app

Native Flutter Android app for [Roti Connect](../README.md), themed off the
poster variant (`../updates0909/handover_poster_variant/`). Talks to the
Django backend's `/api/v1/` JSON API (`../src/public/api.py`,
`../src/public/urls_v1_api.py`).

**Start here:** [`../docs/mobile/FLUTTER_APP_PLAN.md`](../docs/mobile/FLUTTER_APP_PLAN.md)
— the live status board for this app: what's done, what's deliberately
different from the web build's information architecture, and what's still
open. [`../docs/mobile/INSTALL.md`](../docs/mobile/INSTALL.md) has build and
install steps.

## Layout

```
lib/
  app/       go_router setup + the 4-tab bottom nav shell
  data/      models, the dio-based API client, the repository wrapping every
             /api/v1/ endpoint
  features/  one folder per screen (home, menu, basket, checkout, orders,
             account)
  state/     Riverpod providers/notifiers (auth, basket, API data)
  theme/     design tokens ported from the poster style guide + ThemeData
  util/      small helpers (money formatting, idempotency keys)
assets/
  fonts/     Barlow Condensed, converted from the web build's own .woff2
             files (see pubspec.yaml for the regeneration command)
  icon/      app icon source artwork
```

## Common commands

```bash
flutter pub get          # fetch dependencies
flutter analyze          # static analysis — should always be clean
flutter run               # run on a connected device/emulator
flutter build apk --release --split-per-abi   # release APKs, see INSTALL.md
```
