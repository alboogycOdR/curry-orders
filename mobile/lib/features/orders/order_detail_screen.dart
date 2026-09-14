import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models.dart';
import '../../state/api_providers.dart';
import '../../theme/poster_tokens.dart';
import '../../util/money.dart';

/// Order status — the app's JSON equivalent of `public/order_status.html`
/// (five-dot stepper, EFT bank details + proof upload, collection
/// address). Reached from Home's "last order" card, Account's order
/// history, and Checkout's post-place-order redirect.
class OrderDetailScreen extends ConsumerWidget {
  const OrderDetailScreen({super.key, required this.publicToken});

  final String publicToken;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final orderAsync = ref.watch(orderDetailProvider(publicToken));

    return Scaffold(
      appBar: AppBar(title: const Text('Order status')),
      backgroundColor: PosterColors.paper,
      body: orderAsync.when(
        data: (order) => _OrderBody(order: order),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(child: Text('$err', style: PosterText.bodyDefault)),
      ),
    );
  }
}

class _OrderBody extends StatelessWidget {
  const _OrderBody({required this.order});

  final OrderDetail order;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
      children: [
        Text(order.orderNumber, style: PosterText.sectionDisplay.copyWith(fontSize: 32, color: PosterColors.navy)),
        const SizedBox(height: 4),
        Text(order.statusCopy, style: PosterText.bodyLarge),
        const SizedBox(height: 16),
        if (order.stepData != null) _StepperRow(steps: order.stepData!),
        const SizedBox(height: 20),
        _SectionCard(
          title: 'YOUR ORDER',
          child: Column(
            children: [
              for (final line in order.lines)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(child: Text('${line.quantity}× ${line.dishName}')),
                      Text(formatCents(line.lineTotalCents)),
                    ],
                  ),
                ),
              const Divider(),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Total', style: PosterText.cardTitle),
                  Text(formatCents(order.totalCents), style: PosterText.priceCard),
                ],
              ),
            ],
          ),
        ),
        if (order.collectionDate != null || order.collectionSlotLabel != null)
          _SectionCard(
            title: 'COLLECTION',
            child: Text('${order.collectionDate ?? ''}  ${order.collectionSlotLabel ?? ''}'),
          ),
        if (order.collectionAddressLine != null)
          _SectionCard(
            title: 'WHERE',
            child: Text('${order.collectionAddressLine}\n${order.collectionInstructions ?? ''}'.trim()),
          ),
        if (order.eft != null) _EftPanel(eft: order.eft!),
      ],
    );
  }
}

class _StepperRow extends StatelessWidget {
  const _StepperRow({required this.steps});

  final List<StepInfo> steps;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        for (final step in steps)
          Expanded(
            child: Column(
              children: [
                CircleAvatar(
                  radius: 10,
                  backgroundColor: step.active
                      ? PosterColors.gold
                      : step.filled
                          ? PosterColors.navy
                          : PosterColors.border,
                ),
                const SizedBox(height: 4),
                Text(step.label, textAlign: TextAlign.center, style: const TextStyle(fontSize: 9)),
              ],
            ),
          ),
      ],
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: PosterColors.white, borderRadius: BorderRadius.circular(5)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: PosterText.eyebrow.copyWith(color: PosterColors.blue)),
          const SizedBox(height: 8),
          child,
        ],
      ),
    );
  }
}

class _EftPanel extends StatelessWidget {
  const _EftPanel({required this.eft});

  final EftDetail eft;

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      title: 'EFT — PAY INTO THIS ACCOUNT',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _bankRow('Bank', eft.bankName),
          _bankRow('Account name', eft.accountName),
          _bankRow('Account number', eft.accountNumber),
          _bankRow('Branch code', eft.branchCode),
          _bankRow('Account type', eft.accountType),
          _bankRow('Amount', formatCents(eft.amountCents)),
          _bankRow('Reference — use this exact text', eft.reference),
          if (eft.proofAlreadyUploaded)
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text('Proof already uploaded — we\'re checking it.', style: PosterText.bodyDefault),
            ),
          // TODO(Phase 4): native camera/gallery picker (image_picker) →
          // POST /api/v1/orders/<token>/proof/, once proof isn't already
          // uploaded. Not built yet.
        ],
      ),
    );
  }

  Widget _bankRow(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
            Text(value, style: PosterText.bodyDefault.copyWith(fontWeight: FontWeight.w700)),
          ],
        ),
      );
}
