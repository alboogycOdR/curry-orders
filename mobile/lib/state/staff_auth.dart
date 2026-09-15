import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../data/api_exception.dart';
import '../data/staff/staff_api.dart';
import '../data/staff/staff_models.dart';
import 'api_providers.dart';

/// The same web OAuth client every other Google flow in this project
/// uses (`GOOGLE_CLIENT_ID` in the server's own `.env` —
/// `src/core/google_auth.py`) — passed as `serverClientId` so
/// [GoogleSignIn] hands back an ID token audienced for *this server*,
/// not some Android-only client the backend would have no way to
/// verify against. Client IDs are not secret (only the matching client
/// *secret*, never shipped to a client app, is) — embedding this here
/// is the normal, documented way `google_sign_in` is configured.
/// Requires a separate one-time Google Cloud Console step outside this
/// code: an **Android** OAuth client registered under the release
/// keystore's SHA-1 fingerprint, in the same project as this web
/// client — see docs/mobile/FLUTTER_APP_PLAN.md Phase 8.
const _googleServerClientId =
    '32517717084-mul5ga91cvhmal85cfqh3752cgt7de22.apps.googleusercontent.com';

/// Staff-mode auth state — this app's whole auth model since it became
/// staff-only (docs/mobile/FLUTTER_APP_PLAN.md Phase 7, 2026-09-15).
/// `app/staff_shell.dart` watches this directly as the app's auth gate:
/// signed out (or a session that's expired — the staff session's own
/// 12h absolute / 2h idle lifetime, `staff.sessions`) bounces to
/// `/staff/login`.
class StaffAuthState {
  const StaffAuthState({this.user, this.restoring = true});

  final StaffUser? user;
  final bool restoring;

  bool get isStaff => user != null;

  StaffAuthState _copyWith({StaffUser? user, bool? restoring}) =>
      StaffAuthState(user: user, restoring: restoring ?? this.restoring);
}

class StaffAuthNotifier extends StateNotifier<StaffAuthState> {
  StaffAuthNotifier(this._api) : super(const StaffAuthState()) {
    _restore();
  }

  final StaffApi _api;
  final _google = GoogleSignIn(serverClientId: _googleServerClientId, scopes: ['email']);

  Future<void> _restore() async {
    try {
      final user = await _api.me();
      state = StaffAuthState(user: user, restoring: false);
    } on ApiException {
      state = const StaffAuthState(restoring: false);
    }
  }

  Future<void> login({required String email, required String password}) async {
    final user = await _api.login(email: email, password: password);
    state = state._copyWith(user: user, restoring: false);
  }

  /// Runs the on-device Google sign-in flow (account picker, consent
  /// if first time) and, on success, exchanges the resulting ID token
  /// for a staff session via `POST /api/v1/staff/auth/google/`. Throws
  /// `ApiException(code: 'forbidden')` if the chosen Google account
  /// isn't on the staff allowlist — same as [login]'s wrong-password
  /// case, a normal outcome the caller should show inline, not a bug.
  /// Returns `false` (no exception) if the user simply cancels the
  /// account picker — nothing went wrong, there's just nothing to do.
  Future<bool> loginWithGoogle() async {
    final account = await _google.signIn();
    if (account == null) return false; // user cancelled the picker
    final auth = await account.authentication;
    final idToken = auth.idToken;
    if (idToken == null) {
      throw ApiException(
        code: 'validation_error',
        message: 'Google did not return a sign-in token. Please try again.',
        statusCode: 0,
      );
    }
    final user = await _api.googleLogin(idToken: idToken);
    state = state._copyWith(user: user, restoring: false);
    return true;
  }

  /// `staff.sessions.log_out` flushes the whole Django session server-
  /// side (existing, already-shipped web behaviour — see
  /// `api_mobile.logout_json`'s own docstring); harmless now that this
  /// app never establishes a customer session in the first place
  /// (Phase 7 removed that whole side of the app). Also signs out of
  /// Google on-device (`GoogleSignIn.signOut`, a no-op if the last
  /// sign-in was password-based) so a later "Sign in with Google" tap
  /// shows the account picker again rather than silently reusing
  /// whichever Google account was last used here.
  Future<void> logout() async {
    await _api.logout();
    await _google.signOut();
    state = const StaffAuthState(restoring: false);
  }
}

final staffApiProvider = Provider<StaffApi>((ref) => StaffApi(ref.watch(apiClientProvider)));

final staffAuthProvider = StateNotifierProvider<StaffAuthNotifier, StaffAuthState>(
  (ref) => StaffAuthNotifier(ref.watch(staffApiProvider)),
);
