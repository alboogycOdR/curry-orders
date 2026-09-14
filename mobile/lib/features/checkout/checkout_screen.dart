import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/api_exception.dart';
import '../../state/api_providers.dart';
import '../../state/basket.dart';
import '../../theme/poster_tokens.dart';
import '../../util/idempotency.dart';
import '../../util/money.dart';

/// Checkout — one screen with clear sections (review → payment → contact
/// details) rather than the web's single long scrolling form
/// (docs/mobile/FLUTTER_APP_PLAN.md Phase 3 IA note flags this as worth
/// reconsidering; a proper multi-step wizard is a later pass — this is
/// the section-grouped version, a smaller native-shaped step from the
/// web layout without the cost of a full wizard rebuild yet).
class CheckoutScreen extends ConsumerStatefulWidget {
  const CheckoutScreen({super.key});

  @override
  ConsumerState<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends ConsumerState<CheckoutScreen> {
  final _nameController = TextEditingController();
  final _mobileController = TextEditingController();
  final _noteController = TextEditingController();
  String _paymentMethod = 'eft';
  bool _acceptedPolicies = false;
  bool _submitting = false;
  String? _errorMessage;
  Map<String, String>? _fieldErrors;

  @override
  void dispose() {
    _nameController.dispose();
    _mobileController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  Future<void> _placeOrder() async {
    final basket = ref.read(basketProvider);
    if (!basket.hasCollectionChoice || basket.isEmpty) return;
    if (!_acceptedPolicies) {
      setState(() => _errorMessage = 'You must accept the policies to order.');
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
      _fieldErrors = null;
    });

    final payload = {
      'name': _nameController.text.trim(),
      'mobile': _mobileController.text.trim(),
      'note': _noteController.text.trim(),
      'date': basket.collectionDateIso,
      'slot_id': basket.slotId,
      'payment_method': _paymentMethod,
      'collection_method': 'direct',
      'accept_policies': _acceptedPolicies,
      'lines': [
        for (final line in basket.lines)
          {
            'dish_id': line.dishId,
            'quantity': line.quantity,
            'option_value_ids': line.optionValueIds,
            'kitchen_note': line.kitchenNote,
          },
      ],
    };

    try {
      final result = await ref
          .read(apiProvider)
          .checkout(payload, idempotencyKey: generateIdempotencyKey());
      if (!mounted) return;
      ref.read(basketProvider.notifier).clear();
      context.pushReplacement('/orders/${result['public_token']}');
    } on ApiException catch (e) {
      setState(() {
        _errorMessage = e.message;
        _fieldErrors = e.fields;
      });
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final basket = ref.watch(basketProvider);
    final canSubmit = basket.hasCollectionChoice &&
        !basket.isEmpty &&
        _nameController.text.trim().isNotEmpty &&
        _mobileController.text.trim().isNotEmpty &&
        !_submitting;

    return Scaffold(
      appBar: AppBar(title: const Text('Checkout')),
      backgroundColor: PosterColors.paper,
      body: ListView(
        padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
        children: [
          const Text('ORDER SUMMARY', style: PosterText.eyebrow),
          const SizedBox(height: 8),
          for (final line in basket.lines)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      line.optionsSummary.isEmpty
                          ? '${line.quantity}× ${line.name}'
                          : '${line.quantity}× ${line.name} (${line.optionsSummary})',
                    ),
                  ),
                  Text(formatCents(line.lineTotalCents)),
                ],
              ),
            ),
          const Divider(),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Total', style: PosterText.cardTitle),
              Text(formatCents(basket.totalCents), style: PosterText.priceCard),
            ],
          ),
          const SizedBox(height: 24),
          const Text('PAYMENT', style: PosterText.eyebrow),
          RadioGroup<String>(
            groupValue: _paymentMethod,
            onChanged: (v) => setState(() => _paymentMethod = v!),
            child: const Column(
              children: [
                RadioListTile<String>(value: 'eft', title: Text('EFT')),
                RadioListTile<String>(value: 'cash', title: Text('Cash on collection')),
              ],
            ),
          ),
          const SizedBox(height: 16),
          const Text('YOUR DETAILS', style: PosterText.eyebrow),
          const SizedBox(height: 8),
          TextField(
            controller: _nameController,
            decoration: InputDecoration(labelText: 'Full name', errorText: _fieldErrors?['name']),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _mobileController,
            keyboardType: TextInputType.phone,
            decoration: InputDecoration(labelText: 'Mobile number', errorText: _fieldErrors?['mobile']),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _noteController,
            decoration: const InputDecoration(labelText: 'Order note (optional)'),
            maxLength: 200,
          ),
          CheckboxListTile(
            value: _acceptedPolicies,
            onChanged: (v) => setState(() => _acceptedPolicies = v ?? false),
            title: const Text('I accept the ordering policies'),
            controlAffinity: ListTileControlAffinity.leading,
          ),
          if (_errorMessage != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(_errorMessage!, style: const TextStyle(color: PosterColors.error)),
            ),
          ElevatedButton(
            onPressed: canSubmit ? _placeOrder : null,
            child: _submitting
                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('PLACE ORDER'),
          ),
        ],
      ),
    );
  }
}
