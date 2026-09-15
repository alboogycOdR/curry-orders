import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_exception.dart';
import '../data/staff/staff_api.dart';
import '../data/staff/staff_models.dart';
import 'api_providers.dart';

/// Staff-mode auth state — deliberately independent of [AuthState]
/// (`state/auth.dart`, the customer side): a signed-in customer and a
/// signed-in staff member are two separate concerns even though they
/// can coexist in the same Django session (see `StaffApi`'s own
/// docstring). Staff mode is reached from Account (see
/// `features/account/account_screen.dart`'s "Staff dashboard" entry
/// point) but never assumes a customer session exists.
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

  /// Also ends any signed-in *customer* session sharing this cookie —
  /// `staff.sessions.log_out` flushes the whole Django session, not
  /// just the staff half of it (existing, already-shipped web
  /// behaviour — see `api_mobile.logout_json`'s own docstring). The app
  /// should also clear [authProvider]'s state after calling this if a
  /// customer happened to be signed in too.
  Future<void> logout() async {
    await _api.logout();
    state = const StaffAuthState(restoring: false);
  }
}

final staffApiProvider = Provider<StaffApi>((ref) => StaffApi(ref.watch(apiClientProvider)));

final staffAuthProvider = StateNotifierProvider<StaffAuthNotifier, StaffAuthState>(
  (ref) => StaffAuthNotifier(ref.watch(staffApiProvider)),
);
