import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/api_exception.dart';
import '../../state/staff_auth.dart';
import '../../theme/poster_tokens.dart';

/// Staff sign-in — password (`staff/views.py::login`'s own rules) or
/// Google (Phase 8, `staff/services.py::try_grant_staff_session`, the
/// same allowlist check and session-granting code the web's Google
/// button uses). The app's own front door
/// (docs/mobile/FLUTTER_APP_PLAN.md Phase 7 — the app became
/// staff-only 2026-09-15, removing the customer-facing screens this
/// used to sit alongside): `app/staff_shell.dart` bounces here whenever
/// [staffAuthProvider] isn't signed in, and this screen pushes straight
/// to `/staff/inbox` on success either way.
class StaffLoginScreen extends ConsumerStatefulWidget {
  const StaffLoginScreen({super.key});

  @override
  ConsumerState<StaffLoginScreen> createState() => _StaffLoginScreenState();
}

class _StaffLoginScreenState extends ConsumerState<StaffLoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await ref.read(staffAuthProvider.notifier).login(
            email: _emailController.text.trim(),
            password: _passwordController.text,
          );
      if (mounted) context.go('/staff/inbox');
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _submitGoogle() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final signedIn = await ref.read(staffAuthProvider.notifier).loginWithGoogle();
      if (signedIn && mounted) context.go('/staff/inbox');
      // signedIn == false means the user cancelled the account picker —
      // nothing went wrong, just stay on this screen quietly.
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PosterColors.navy,
      appBar: AppBar(backgroundColor: PosterColors.navy, foregroundColor: PosterColors.white, elevation: 0),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
          children: [
            const Text('STAFF SIGN IN', style: PosterText.eyebrow, textAlign: TextAlign.left),
            const SizedBox(height: 4),
            Text('Kitchen & office access', style: PosterText.cardTitle.copyWith(color: PosterColors.white)),
            const SizedBox(height: 24),
            OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                backgroundColor: PosterColors.white,
                foregroundColor: PosterColors.navy,
                side: const BorderSide(color: PosterColors.border),
                minimumSize: const Size.fromHeight(48),
              ),
              onPressed: _submitting ? null : _submitGoogle,
              // A plain "G" mark rather than pulling in a logo asset —
              // no brand-asset package/SVG dependency needed for one
              // button; PosterColors.blue keeps it in the app's own
              // palette rather than Google's literal brand colours.
              icon: const Text('G', style: TextStyle(fontWeight: FontWeight.w900, color: PosterColors.blue)),
              label: const Text('SIGN IN WITH GOOGLE', style: PosterText.button),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                const Expanded(child: Divider(color: PosterColors.bluePanel)),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  child: Text('OR', style: PosterText.eyebrow.copyWith(color: PosterColors.mutedDark)),
                ),
                const Expanded(child: Divider(color: PosterColors.bluePanel)),
              ],
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _emailController,
              keyboardType: TextInputType.emailAddress,
              style: const TextStyle(color: PosterColors.navy),
              decoration: const InputDecoration(
                labelText: 'Email',
                filled: true,
                fillColor: PosterColors.white,
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _passwordController,
              obscureText: true,
              style: const TextStyle(color: PosterColors.navy),
              decoration: const InputDecoration(
                labelText: 'Password',
                filled: true,
                fillColor: PosterColors.white,
              ),
              onSubmitted: (_) => _submitting ? null : _submit(),
            ),
            const SizedBox(height: 16),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(_error!, style: const TextStyle(color: PosterColors.gold)),
              ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: PosterColors.gold,
                foregroundColor: PosterColors.navy,
                minimumSize: const Size.fromHeight(48),
              ),
              onPressed: _submitting ? null : _submit,
              child: _submitting
                  ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('SIGN IN', style: PosterText.button),
            ),
          ],
        ),
      ),
    );
  }
}
