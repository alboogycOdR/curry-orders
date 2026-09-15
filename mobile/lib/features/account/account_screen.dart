import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/api_exception.dart';
import '../../data/models.dart';
import '../../state/api_providers.dart';
import '../../state/auth.dart';
import '../../state/staff_auth.dart';
import '../../theme/poster_tokens.dart';
import '../../util/money.dart';

/// Account — profile + sign-in/up + order history + guest order lookup,
/// all in one place. Deliberately merges what the poster web build
/// leaves as "no tab of its own" (Account) with what it treats as a
/// separate guest-first flow (order lookup) — see
/// docs/mobile/FLUTTER_APP_PLAN.md Phase 3 IA note and `app/shell.dart`'s
/// own docstring for the reasoning.
class AccountScreen extends ConsumerWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);

    return ColoredBox(
      color: PosterColors.paper,
      child: SafeArea(
        child: auth.restoring
            ? const Center(child: CircularProgressIndicator())
            : auth.isSignedIn
                ? _SignedInBody(customer: auth.customer!)
                : const _SignedOutBody(),
      ),
    );
  }
}

class _SignedInBody extends ConsumerWidget {
  const _SignedInBody({required this.customer});

  final CustomerAccount customer;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(accountOrdersProvider);

    return ListView(
      padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
      children: [
        Row(
          children: [
            const CircleAvatar(radius: 22, backgroundColor: PosterColors.bluePanel, child: Icon(Icons.person, color: PosterColors.white)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(customer.fullName, style: PosterText.cardTitle.copyWith(color: PosterColors.navy)),
                  Text(customer.mobileE164, style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
                ],
              ),
            ),
            TextButton(
              onPressed: () => ref.read(authProvider.notifier).logout(),
              child: const Text('SIGN OUT'),
            ),
          ],
        ),
        const SizedBox(height: 24),
        const Text('YOUR ORDERS', style: PosterText.eyebrow),
        const SizedBox(height: 8),
        ordersAsync.when(
          data: (orders) => orders.isEmpty
              ? const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Text('No orders yet.', style: PosterText.bodyDefault),
                )
              : Column(children: [for (final order in orders) _OrderSummaryRow(order: order)]),
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (err, _) => Text('$err', style: PosterText.bodyDefault),
        ),
        const SizedBox(height: 32),
        const _StaffEntryPoint(),
      ],
    );
  }
}

/// Staff mode's own entry point (docs/mobile/FLUTTER_APP_PLAN.md Phase
/// 6) — independent of the customer sign-in state above: a device can
/// be signed in as a customer, staff, both, or neither, since the two
/// sessions coexist. Low-emphasis when not staff (a plain text link,
/// matching the web footer's always-present but unobtrusive "Staff
/// login"), a real card once `staffAuthProvider` confirms a staff
/// session exists.
class _StaffEntryPoint extends ConsumerWidget {
  const _StaffEntryPoint();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final staffAuth = ref.watch(staffAuthProvider);
    if (staffAuth.restoring) return const SizedBox.shrink();

    if (staffAuth.isStaff) {
      final user = staffAuth.user!;
      return Container(
        decoration: BoxDecoration(color: PosterColors.navy, borderRadius: BorderRadius.circular(5)),
        child: ListTile(
          leading: const Icon(Icons.badge_rounded, color: PosterColors.gold),
          title: Text('Staff dashboard', style: PosterText.cardTitle.copyWith(fontSize: 16, color: PosterColors.white)),
          subtitle: Text('${user.name} · ${user.roleDisplay}', style: const TextStyle(color: PosterColors.mutedDark)),
          trailing: const Icon(Icons.arrow_forward_rounded, color: PosterColors.white),
          onTap: () => context.push('/staff/inbox'),
        ),
      );
    }

    return Center(
      child: TextButton.icon(
        onPressed: () => context.push('/staff/login'),
        icon: const Icon(Icons.badge_outlined, size: 16, color: PosterColors.muted),
        label: const Text('Kitchen staff sign in', style: TextStyle(color: PosterColors.muted)),
      ),
    );
  }
}

class _OrderSummaryRow extends StatelessWidget {
  const _OrderSummaryRow({required this.order});

  final OrderSummary order;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(color: PosterColors.white, borderRadius: BorderRadius.circular(5)),
      child: ListTile(
        title: Text(order.orderNumber, style: PosterText.cardTitle.copyWith(fontSize: 16, color: PosterColors.navy)),
        subtitle: Text(order.statusCopy),
        trailing: Text(formatCents(order.totalCents)),
        onTap: () => context.push('/orders/${order.publicToken}'),
      ),
    );
  }
}

class _SignedOutBody extends ConsumerStatefulWidget {
  const _SignedOutBody();

  @override
  ConsumerState<_SignedOutBody> createState() => _SignedOutBodyState();
}

enum _Mode { login, signup, lookup }

class _SignedOutBodyState extends ConsumerState<_SignedOutBody> {
  _Mode _mode = _Mode.login;
  final _nameController = TextEditingController();
  final _mobileController = TextEditingController();
  final _passwordController = TextEditingController();
  final _orderNumberController = TextEditingController();
  bool _submitting = false;
  String? _error;
  List<OrderDetail>? _lookupResults;

  @override
  void dispose() {
    _nameController.dispose();
    _mobileController.dispose();
    _passwordController.dispose();
    _orderNumberController.dispose();
    super.dispose();
  }

  Future<void> _submitAuth() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      if (_mode == _Mode.login) {
        await ref.read(authProvider.notifier).login(
              mobile: _mobileController.text.trim(),
              password: _passwordController.text,
            );
      } else {
        await ref.read(authProvider.notifier).signup(
              name: _nameController.text.trim(),
              mobile: _mobileController.text.trim(),
              password: _passwordController.text,
            );
      }
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _submitLookup() async {
    setState(() {
      _submitting = true;
      _error = null;
      _lookupResults = null;
    });
    try {
      final results = await ref.read(apiProvider).lookup(
            orderNumber: _orderNumberController.text.trim(),
            mobile: _mobileController.text.trim(),
          );
      setState(() => _lookupResults = results);
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
      children: [
        const Text('ACCOUNT', style: PosterText.eyebrow),
        const SizedBox(height: 8),
        SegmentedButton<_Mode>(
          segments: const [
            ButtonSegment(value: _Mode.login, label: Text('Sign in')),
            ButtonSegment(value: _Mode.signup, label: Text('Sign up')),
            ButtonSegment(value: _Mode.lookup, label: Text('Find order')),
          ],
          selected: {_mode},
          onSelectionChanged: (s) => setState(() {
            _mode = s.first;
            _error = null;
            _lookupResults = null;
          }),
        ),
        const SizedBox(height: 16),
        if (_mode == _Mode.signup)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: TextField(controller: _nameController, decoration: const InputDecoration(labelText: 'Full name')),
          ),
        if (_mode == _Mode.lookup)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: TextField(
              controller: _orderNumberController,
              decoration: const InputDecoration(labelText: 'Order number (e.g. CT-260101-0001)'),
            ),
          ),
        TextField(
          controller: _mobileController,
          keyboardType: TextInputType.phone,
          decoration: const InputDecoration(labelText: 'Mobile number'),
        ),
        if (_mode != _Mode.lookup) ...[
          const SizedBox(height: 12),
          TextField(
            controller: _passwordController,
            obscureText: true,
            decoration: const InputDecoration(labelText: 'Password'),
          ),
        ],
        const SizedBox(height: 16),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(_error!, style: const TextStyle(color: PosterColors.error)),
          ),
        ElevatedButton(
          onPressed: _submitting ? null : (_mode == _Mode.lookup ? _submitLookup : _submitAuth),
          child: _submitting
              ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
              : Text(switch (_mode) {
                  _Mode.login => 'SIGN IN',
                  _Mode.signup => 'CREATE ACCOUNT',
                  _Mode.lookup => 'FIND ORDER',
                }),
        ),
        if (_lookupResults != null)
          for (final order in _lookupResults!)
            Card(
              child: ListTile(
                title: Text(order.orderNumber),
                subtitle: Text(order.statusCopy),
                onTap: () => context.push('/orders/${order.publicToken}'),
              ),
            ),
        const SizedBox(height: 32),
        const _StaffEntryPoint(),
      ],
    );
  }
}
