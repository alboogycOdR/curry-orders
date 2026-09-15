import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_exception.dart';
import '../data/staff/staff_api.dart';
import '../data/staff/staff_models.dart';
import 'api_providers.dart';

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

  /// `staff.sessions.log_out` flushes the whole Django session server-
  /// side (existing, already-shipped web behaviour — see
  /// `api_mobile.logout_json`'s own docstring); harmless now that this
  /// app never establishes a customer session in the first place
  /// (Phase 7 removed that whole side of the app).
  Future<void> logout() async {
    await _api.logout();
    state = const StaffAuthState(restoring: false);
  }
}

final staffApiProvider = Provider<StaffApi>((ref) => StaffApi(ref.watch(apiClientProvider)));

final staffAuthProvider = StateNotifierProvider<StaffAuthNotifier, StaffAuthState>(
  (ref) => StaffAuthNotifier(ref.watch(staffApiProvider)),
);
