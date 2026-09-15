import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Battery-optimisation exemption (mobile Phase 9) — a small hand-written
/// platform channel (`android/app/.../MainActivity.kt`) rather than a
/// package: this is two one-line `PowerManager`/`Settings` calls, not
/// worth a whole extra dependency for.
///
/// Why this matters specifically for *this* app: several Android OEM
/// battery managers (Xiaomi/MIUI, Huawei, Oppo/ColorOS, and others —
/// not stock Android's own Doze mode, which Firebase Cloud Messaging
/// already handles correctly on its own) kill backgrounded apps
/// aggressively enough to silently stop push notifications arriving,
/// with no error anywhere to explain why. A kitchen device that's
/// meant to reliably alert staff the moment an order comes in needs
/// this exemption explicitly requested, not assumed.
class BatteryOptimizationService {
  static const _channel = MethodChannel('roti_connect/battery_optimization');

  Future<bool> isIgnoringBatteryOptimizations() async {
    final result = await _channel.invokeMethod<bool>('isIgnoringBatteryOptimizations');
    return result ?? false;
  }

  /// Opens Android's own "allow this app to ignore battery
  /// optimisations?" dialog — the user still has to confirm it there,
  /// this only opens it. Safe to call even when already exempted
  /// (Android just closes it immediately).
  Future<void> requestExemption() => _channel.invokeMethod<void>('requestIgnoreBatteryOptimizations');

  /// Fallback for the rare OEM skin where the direct-request intent
  /// above isn't supported — opens the general "ignore optimisations"
  /// settings list instead.
  Future<void> openSettings() => _channel.invokeMethod<void>('openBatteryOptimizationSettings');
}

final batteryOptimizationServiceProvider = Provider<BatteryOptimizationService>(
  (ref) => BatteryOptimizationService(),
);

/// Re-checked every time this is watched after a rebuild (e.g. on
/// returning from the system dialog) via `ref.invalidate` from the
/// screen that shows it — not cached across the whole app lifetime,
/// since the user can flip this in system Settings at any time outside
/// the app's own control.
final isIgnoringBatteryOptimizationsProvider = FutureProvider<bool>((ref) {
  return ref.watch(batteryOptimizationServiceProvider).isIgnoringBatteryOptimizations();
});
