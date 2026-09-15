import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state/biometric_auth.dart';
import '../../theme/poster_tokens.dart';

/// Shown by `app/staff_shell.dart` whenever fingerprint sign-in is on
/// (`state/biometric_auth.dart`) and this process hasn't unlocked yet —
/// cold start, or coming back from the background. Prompts immediately
/// on first build; if the user cancels or the sensor fails, they land
/// here with a retry button rather than being silently stuck (a broken
/// or dirty sensor should never be able to lock someone out of a
/// kitchen device with no way back in).
class BiometricLockScreen extends ConsumerStatefulWidget {
  const BiometricLockScreen({super.key});

  @override
  ConsumerState<BiometricLockScreen> createState() => _BiometricLockScreenState();
}

class _BiometricLockScreenState extends ConsumerState<BiometricLockScreen> {
  bool _checking = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _tryUnlock());
  }

  Future<void> _tryUnlock() async {
    setState(() => _checking = true);
    await ref.read(biometricAuthProvider.notifier).unlock();
    if (mounted) setState(() => _checking = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PosterColors.navy,
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.fingerprint_rounded, color: PosterColors.gold, size: 72),
                const SizedBox(height: 16),
                Text(
                  'Unlock with your fingerprint',
                  style: PosterText.cardTitle.copyWith(color: PosterColors.white),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                if (_checking)
                  const CircularProgressIndicator(color: PosterColors.gold)
                else
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: PosterColors.gold,
                      foregroundColor: PosterColors.navy,
                      minimumSize: const Size(200, 48),
                    ),
                    onPressed: _tryUnlock,
                    child: const Text('TRY AGAIN', style: PosterText.button),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
