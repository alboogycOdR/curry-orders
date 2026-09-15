import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/api_exception.dart';
import '../../state/staff_auth.dart';
import '../../theme/poster_tokens.dart';

/// Staff sign-in (docs/mobile/FLUTTER_APP_PLAN.md Phase 6) — email +
/// password only, same as the web's own primary login path
/// (`staff/views.py::login`). Independent of the customer
/// [authProvider]/login screen: staff mode has its own session check
/// (`staffAuthProvider`) and its own credentials, reached from
/// Account's "Staff dashboard" entry card, not from the customer
/// sign-in form. Google sign-in for staff (web has it,
/// `staff/services.py::try_grant_staff_session`) isn't wired into the
/// app yet — same open gap as customer Google sign-in, tracked
/// separately, not part of this phase.
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
