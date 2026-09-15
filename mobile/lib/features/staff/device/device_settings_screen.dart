import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state/battery_optimization.dart';
import '../../../state/biometric_auth.dart';
import '../../../theme/poster_tokens.dart';
import '../staff_scaffold.dart';

/// Device-level settings that only make sense per-phone, not as part
/// of the shared, owner/admin-only business `core.models.Settings` —
/// battery-optimisation exemption and fingerprint sign-in (mobile
/// Phase 9). Same reasoning `state/notifications.dart` already
/// documents for why its own toggle lives outside Settings too; kept
/// as its own screen/More row rather than folded into Notifications,
/// since these two are a different *kind* of device concern (security
/// and reliability, not "do I want alerts").
class DeviceSettingsScreen extends ConsumerWidget {
  const DeviceSettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return StaffScaffold(
      title: 'Device settings',
      body: ListView(
        padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
        children: const [
          _BiometricSection(),
          SizedBox(height: 24),
          _BatterySection(),
        ],
      ),
    );
  }
}

class _BiometricSection extends ConsumerWidget {
  const _BiometricSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final availableAsync = ref.watch(_biometricAvailableProvider);
    final biometric = ref.watch(biometricAuthProvider);

    return availableAsync.when(
      // "if that option is available" (explicit direction) — no
      // section at all on a device with no fingerprint/face sensor
      // enrolled, not a disabled toggle explaining why.
      data: (available) => !available
          ? const SizedBox.shrink()
          : _SettingsCard(
              icon: Icons.fingerprint_rounded,
              title: 'Fingerprint sign-in',
              subtitle: 'Unlock with your fingerprint instead of typing your '
                  'password every time you open the app.',
              trailing: Switch(
                value: biometric.enabled,
                activeThumbColor: PosterColors.blue,
                onChanged: (value) => _toggle(context, ref, value),
              ),
            ),
      loading: () => const SizedBox.shrink(),
      error: (err, _) => const SizedBox.shrink(),
    );
  }

  Future<void> _toggle(BuildContext context, WidgetRef ref, bool value) async {
    final notifier = ref.read(biometricAuthProvider.notifier);
    final ok = await notifier.setEnabled(value);
    if (!ok && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't verify your fingerprint — nothing changed.")),
      );
    }
  }
}

final _biometricAvailableProvider = FutureProvider<bool>((ref) {
  return ref.watch(biometricAuthServiceProvider).isAvailable();
});

class _BatterySection extends ConsumerWidget {
  const _BatterySection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final exemptAsync = ref.watch(isIgnoringBatteryOptimizationsProvider);

    return _SettingsCard(
      icon: Icons.battery_charging_full_rounded,
      title: 'Battery optimisation',
      subtitle: exemptAsync.when(
        data: (exempt) => exempt
            ? 'This device is already excluded from battery optimisation — '
                "order alerts won't be delayed or blocked."
            : 'Some phones silently block alerts to save battery. Exclude this '
                'app so order alerts always arrive on time.',
        loading: () => 'Checking…',
        error: (err, _) => "Couldn't check this device's battery settings.",
      ),
      trailing: exemptAsync.maybeWhen(
        data: (exempt) => exempt
            ? const Icon(Icons.check_circle_rounded, color: PosterColors.success)
            : TextButton(
                onPressed: () async {
                  await ref.read(batteryOptimizationServiceProvider).requestExemption();
                  ref.invalidate(isIgnoringBatteryOptimizationsProvider);
                },
                child: const Text('FIX'),
              ),
        orElse: () => null,
      ),
    );
  }
}

class _SettingsCard extends StatelessWidget {
  const _SettingsCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.trailing,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PosterColors.white,
        borderRadius: BorderRadius.circular(PosterSpace.radiusButton),
        border: Border.all(color: PosterColors.border),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: const BoxDecoration(color: PosterColors.bluePanel, shape: BoxShape.circle),
            child: Icon(icon, color: PosterColors.gold),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: PosterText.cardTitle.copyWith(fontSize: 16, color: PosterColors.navy)),
                const SizedBox(height: 2),
                Text(subtitle, style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
              ],
            ),
          ),
          if (trailing != null) ...[const SizedBox(width: 8), trailing!],
        ],
      ),
    );
  }
}
