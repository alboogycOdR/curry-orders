import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_auth/local_auth.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_providers.dart';

/// Fingerprint (or whatever biometric the device offers — face unlock
/// counts too, `local_auth` abstracts over both) sign-in (mobile Phase
/// 9). Deliberately **not** a way to authenticate with the server on
/// its own — biometrics never touch a password or any server
/// credential. What it actually gates is *resuming* an already-
/// established session that now persists across app restarts
/// (`data/api_client.dart`'s `PersistCookieJar`): with the preference
/// on, opening the app (cold start) or bringing it back from the
/// background requires a successful fingerprint check before the
/// persisted session is usable, the same way a banking app's
/// "biometric unlock" works — a fresh sign-in (password or Google)
/// still always works regardless of this setting, and a session that's
/// genuinely expired server-side still lands on the login screen after
/// a successful fingerprint check, not a bypass of anything real.
///
/// "if that option is available" (explicit direction): the Notifications-
/// adjacent settings screen only shows this toggle when
/// [BiometricAuthService.isAvailable] is true — a device with no
/// fingerprint/face sensor enrolled simply doesn't see it.
class BiometricAuthService {
  final _auth = LocalAuthentication();

  Future<bool> isAvailable() async {
    final canCheck = await _auth.canCheckBiometrics;
    final supported = await _auth.isDeviceSupported();
    if (!canCheck || !supported) return false;
    final available = await _auth.getAvailableBiometrics();
    return available.isNotEmpty;
  }

  Future<bool> authenticate() async {
    try {
      return await _auth.authenticate(
        localizedReason: 'Unlock Roti Connect Staff',
        options: const AuthenticationOptions(biometricOnly: true, stickyAuth: true),
      );
    } on Exception {
      // A real sensor/OS-level failure (not just "wrong finger" — that
      // resolves through the system's own retry UI without throwing)
      // -- treat it the same as a declined check rather than crash the
      // app: whatever screen called this shows the normal "try again"
      // path either way.
      return false;
    }
  }
}

final biometricAuthServiceProvider = Provider<BiometricAuthService>((ref) => BiometricAuthService());

const _prefsKey = 'biometric_signin_enabled';

/// `enabled`: the persisted user preference. `unlocked`: this
/// *process's* current session — starts `false` every cold start, and
/// is also reset to `false` whenever the app is backgrounded
/// (`app/staff_shell.dart`'s own `AppLifecycleState` observer) so
/// leaving the app and coming back re-gates it, not just a fresh
/// launch. When `enabled` is `false`, `unlocked` is meaningless (the
/// gate in `StaffShell` only checks it while `enabled` is `true`) but
/// kept `true` so toggling the preference off mid-session doesn't
/// itself lock someone out.
class BiometricAuthState {
  const BiometricAuthState({required this.enabled, required this.unlocked});

  final bool enabled;
  final bool unlocked;

  BiometricAuthState _copyWith({bool? enabled, bool? unlocked}) =>
      BiometricAuthState(enabled: enabled ?? this.enabled, unlocked: unlocked ?? this.unlocked);
}

class BiometricAuthNotifier extends StateNotifier<BiometricAuthState> {
  BiometricAuthNotifier(this._ref) : super(const BiometricAuthState(enabled: false, unlocked: true)) {
    _restore();
  }

  final Ref _ref;

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    final enabled = prefs.getBool(_prefsKey) ?? false;
    // A fresh launch with the preference already on starts locked —
    // the whole point of the feature. `unlocked: true` above is only
    // the safe default before this restore completes (matches
    // `enabled: false`, so nothing is gated in that brief window).
    state = BiometricAuthState(enabled: enabled, unlocked: !enabled);
  }

  /// Turning it *on* requires proving biometrics actually work on this
  /// device right now — a stale "on" preference from a device whose
  /// sensor stopped working would otherwise lock someone out with no
  /// way back in short of clearing app data. Turning it *off* also
  /// wipes the persisted session (`ApiClient.clearCookies`): leaving it
  /// merely disabled but still resumable defeats the point of having
  /// offered the extra gate in the first place.
  Future<bool> setEnabled(bool enabled) async {
    if (enabled) {
      final ok = await _ref.read(biometricAuthServiceProvider).authenticate();
      if (!ok) return false;
    } else {
      await _ref.read(apiClientProvider).clearCookies();
    }
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_prefsKey, enabled);
    state = state._copyWith(enabled: enabled, unlocked: true);
    return true;
  }

  void lock() {
    if (state.enabled) state = state._copyWith(unlocked: false);
  }

  Future<bool> unlock() async {
    final ok = await _ref.read(biometricAuthServiceProvider).authenticate();
    if (ok) state = state._copyWith(unlocked: true);
    return ok;
  }
}

final biometricAuthProvider = StateNotifierProvider<BiometricAuthNotifier, BiometricAuthState>(
  (ref) => BiometricAuthNotifier(ref),
);
