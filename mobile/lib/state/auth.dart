import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_exception.dart';
import '../data/models.dart';
import '../data/repository.dart';
import 'api_providers.dart';

/// `restoring` is only true during the app-start session check
/// ([AuthNotifier._restore]) — after that, `customer == null` reliably
/// means "signed out", so screens can branch on it directly instead of
/// juggling a separate loading flag everywhere.
class AuthState {
  const AuthState({this.customer, this.restoring = true});

  final CustomerAccount? customer;
  final bool restoring;

  bool get isSignedIn => customer != null;

  AuthState _copyWith({CustomerAccount? customer, bool? restoring}) =>
      AuthState(customer: customer, restoring: restoring ?? this.restoring);
}

/// Wraps the account endpoints in one place (docs/mobile/FLUTTER_APP_PLAN.md
/// Phase 3's IA note: Account is a real, persistent part of this app, not
/// an afterthought reachable only via a modal like the poster web build).
class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier(this._api) : super(const AuthState()) {
    _restore();
  }

  final RotiConnectApi _api;

  Future<void> _restore() async {
    try {
      final customer = await _api.account();
      state = AuthState(customer: customer, restoring: false);
    } on ApiException {
      // No session yet (auth_required) or the server's unreachable —
      // either way, land on "signed out" rather than stay stuck loading.
      state = const AuthState(restoring: false);
    }
  }

  Future<void> login({required String mobile, required String password}) async {
    final customer = await _api.login(mobile: mobile, password: password);
    state = state._copyWith(customer: customer, restoring: false);
  }

  Future<void> signup({required String name, required String mobile, required String password}) async {
    final customer = await _api.signup(name: name, mobile: mobile, password: password);
    state = state._copyWith(customer: customer, restoring: false);
  }

  Future<void> logout() async {
    await _api.logout();
    state = const AuthState(restoring: false);
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>(
  (ref) => AuthNotifier(ref.watch(apiProvider)),
);

final accountOrdersProvider = FutureProvider<List<OrderSummary>>((ref) {
  ref.watch(authProvider); // re-fetch whenever sign-in state changes
  return ref.watch(apiProvider).accountOrders();
});
