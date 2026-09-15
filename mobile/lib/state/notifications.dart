import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

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
/// This flag alone doesn't yet make push notifications arrive — actual
/// delivery needs Firebase Cloud Messaging wired in (a Firebase
/// project + `google-services.json`, in progress the same day this
/// was built; see the Phase 8 section for exactly what's done vs.
/// pending). Toggling this off should always be honoured immediately
/// once FCM lands (skip token registration / unregister); toggling it
/// on when FCM isn't wired yet just remembers the preference for when
/// it is, rather than erroring.
const _prefsKey = 'notifications_enabled';

class NotificationsPrefsNotifier extends StateNotifier<bool> {
  NotificationsPrefsNotifier() : super(false) {
    _restore();
  }

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    state = prefs.getBool(_prefsKey) ?? false;
  }

  Future<void> setEnabled(bool enabled) async {
    state = enabled;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_prefsKey, enabled);
  }
}

final notificationsEnabledProvider =
    StateNotifierProvider<NotificationsPrefsNotifier, bool>((ref) => NotificationsPrefsNotifier());
