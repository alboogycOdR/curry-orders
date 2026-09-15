import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_providers.dart';

/// Shows a brief banner for a push that arrives while the app is open
/// and in the foreground — Android does NOT surface a system
/// notification for a foreground FCM message on its own (only for
/// background/terminated), so without this, "on" would silently do
/// nothing while the app happens to be the thing in front of the
/// user. Set once, from `main.dart`'s `MaterialApp.router`
/// (`scaffoldMessengerKey:`), so this file doesn't need a `BuildContext`
/// of its own to show it.
final rootScaffoldMessengerKey = GlobalKey<ScaffoldMessengerState>();

/// Per-device "do I want order alerts" preference
/// (docs/mobile/FLUTTER_APP_PLAN.md Phase 8) — deliberately a plain
/// local device setting, not a field on the shared `core.models.
/// Settings` singleton (`features/staff/settings/staff_settings_screen.dart`):
/// that screen is the owner/admin-only *business* config, one row for
/// the whole team; whether *this device* should buzz when a new order
/// comes in is a per-person, per-phone choice, and gating it behind
/// admin access would stop the actual kitchen staff who need the alert
/// most from ever turning it on. Reached from the More tab's
/// "Notifications" row, not nested inside Settings, for that reason.
///
/// Turning this on requests notification permission, fetches this
/// device's FCM token, and registers it with `POST /api/v1/staff/
/// notifications/register/`; turning it off unregisters that token
/// (`.../unregister/`) so this device stops receiving pushes
/// immediately. `_api.googleLogin`-style ApiExceptions from either call
/// are swallowed here (logged, not surfaced) — a registration hiccup
/// shouldn't block the user from flipping a toggle, and the next
/// successful `me()`/app-open retry (`reapplyIfEnabled`) covers a
/// transient failure.
const _prefsKey = 'notifications_enabled';

class NotificationsPrefsNotifier extends StateNotifier<bool> {
  NotificationsPrefsNotifier(this._ref) : super(false) {
    _restore();
    _listenForTokenRefresh();
  }

  final Ref _ref;
  StreamSubscription<String>? _tokenRefreshSub;

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    state = prefs.getBool(_prefsKey) ?? false;
  }

  /// Called once at app start (`main.dart`) — if a previous session
  /// left this switched on, re-register this launch's token without
  /// making the user revisit the Notifications screen. A fresh install
  /// starts with the preference off, so this is a no-op then.
  Future<void> reapplyIfEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    if (prefs.getBool(_prefsKey) ?? false) {
      await _registerToken();
    }
  }

  Future<void> setEnabled(bool enabled) async {
    state = enabled;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_prefsKey, enabled);
    if (enabled) {
      await _registerToken();
    } else {
      await _unregisterCurrentToken();
    }
  }

  Future<void> _registerToken() async {
    final settings = await FirebaseMessaging.instance.requestPermission();
    if (settings.authorizationStatus == AuthorizationStatus.denied) {
      // The OS-level permission prompt was declined — leave the
      // in-app preference as the user set it (they can retry from
      // system Settings and flip this again), don't silently flip it
      // back off behind their back.
      return;
    }
    final token = await FirebaseMessaging.instance.getToken();
    if (token == null) return;
    try {
      final dio = _ref.read(apiClientProvider).dio;
      await dio.post<dynamic>('staff/notifications/register/', data: {'fcm_token': token});
    } catch (_) {
      // Best-effort — see this class's own docstring for why a
      // registration hiccup doesn't surface as an error here.
    }
  }

  Future<void> _unregisterCurrentToken() async {
    final token = await FirebaseMessaging.instance.getToken();
    if (token == null) return;
    try {
      final dio = _ref.read(apiClientProvider).dio;
      await dio.post<dynamic>('staff/notifications/unregister/', data: {'fcm_token': token});
    } catch (_) {
      // Best-effort, same reasoning as _registerToken.
    }
  }

  /// Google Play Services can rotate a device's FCM token at any time
  /// (not just on reinstall) — without re-registering the new one, a
  /// staff member who turned alerts on would silently stop receiving
  /// them whenever that happens, with no visible symptom to explain
  /// why. Re-registration is itself idempotent server-side
  /// (`api_mobile.register_device_token_json`'s own `update_or_create`
  /// on the token value).
  void _listenForTokenRefresh() {
    _tokenRefreshSub = FirebaseMessaging.instance.onTokenRefresh.listen((_) {
      if (state) _registerToken();
    });
  }

  @override
  void dispose() {
    _tokenRefreshSub?.cancel();
    super.dispose();
  }
}

final notificationsEnabledProvider =
    StateNotifierProvider<NotificationsPrefsNotifier, bool>(
  (ref) => NotificationsPrefsNotifier(ref),
);

/// Wires up the foreground-message banner (see [rootScaffoldMessengerKey]'s
/// own docstring) — read once from `main.dart` so it's active for the
/// whole app lifetime, not per-screen.
void listenForForegroundMessages() {
  FirebaseMessaging.onMessage.listen((message) {
    final notification = message.notification;
    if (notification == null) return;
    rootScaffoldMessengerKey.currentState?.showSnackBar(
      SnackBar(
        content: Text('${notification.title ?? 'Order update'}: ${notification.body ?? ''}'),
        duration: const Duration(seconds: 4),
      ),
    );
  });
}
