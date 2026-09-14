import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../data/api_exception.dart';
import '../../data/models.dart';
import '../../state/api_providers.dart';
import '../../state/basket.dart';
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

class _OrderBody extends ConsumerStatefulWidget {
  const _OrderBody({required this.order});

  final OrderDetail order;

  @override
  ConsumerState<_OrderBody> createState() => _OrderBodyState();
}

class _OrderBodyState extends ConsumerState<_OrderBody> {
  bool _reordering = false;

  Future<void> _reorder() async {
    setState(() => _reordering = true);
    try {
      final result = await ref.read(apiProvider).reorder(widget.order.publicToken);
      for (final line in result.lines) {
        ref.read(basketProvider.notifier).addLine(
              dishId: line.dishId,
              name: line.dishName,
              unitPriceCents: line.unitPriceCents,
              optionValueIds: line.optionValueIds,
              optionsSummary: line.optionsSummary,
              quantity: line.quantity,
            );
      }
      if (!mounted) return;
      if (result.droppedDishNames.isNotEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('No longer available: ${result.droppedDishNames.join(', ')}')),
        );
      }
      context.go('/basket');
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _reordering = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final order = widget.order;
    return ListView(
      padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
      children: [
        Text(order.orderNumber, style: PosterText.sectionDisplay.copyWith(fontSize: 32, color: PosterColors.navy)),
        const SizedBox(height: 4),
        Text(order.statusCopy, style: PosterText.bodyLarge),
        const SizedBox(height: 16),
        if (order.stepData != null) _StepperRow(steps: order.stepData!),
        if (order.canReorder)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: ElevatedButton(
              onPressed: _reordering ? null : _reorder,
              child: _reordering
                  ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('ORDER THESE AGAIN'),
            ),
          ),
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
        if (order.eft != null) _EftPanel(eft: order.eft!, publicToken: order.publicToken),
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

class _EftPanel extends ConsumerStatefulWidget {
  const _EftPanel({required this.eft, required this.publicToken});

  final EftDetail eft;
  final String publicToken;

  @override
  ConsumerState<_EftPanel> createState() => _EftPanelState();
}

class _EftPanelState extends ConsumerState<_EftPanel> {
  bool _uploading = false;

  Future<void> _pickAndUpload(ImageSource source) async {
    final picked = await ImagePicker().pickImage(source: source);
    if (picked == null) return;
    setState(() => _uploading = true);
    try {
      await ref.read(apiProvider).uploadProof(widget.publicToken, file: File(picked.path));
      if (!mounted) return;
      ref.invalidate(orderDetailProvider(widget.publicToken));
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Proof uploaded — we\'re checking it.')),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  Future<void> _choosePickerSource() async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_camera),
              title: const Text('Take a photo'),
              onTap: () => Navigator.pop(sheetContext, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library),
              title: const Text('Choose from gallery'),
              onTap: () => Navigator.pop(sheetContext, ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (source != null) await _pickAndUpload(source);
  }

  @override
  Widget build(BuildContext context) {
    final eft = widget.eft;
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
            )
          else
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _uploading ? null : _choosePickerSource,
                  child: _uploading
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('UPLOAD PROOF OF PAYMENT'),
                ),
              ),
            ),
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
