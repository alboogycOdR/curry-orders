import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api_exception.dart';
import '../../../data/staff/staff_api.dart';
import '../../../state/api_providers.dart';
import '../../../theme/poster_tokens.dart';
import '../../../util/money.dart';
import '../staff_scaffold.dart';

/// Cash requests queue (§12.2/M7) — spec-driven mobile port of `staff/
/// templates/staff/cash_requests.html` + `static/js/cash_requests.js`.
/// Backend: `GET /api/v1/staff/cash/`
/// (`staff/api_mobile_collection_cash.py::cash_json`). Accept/Reject
/// POST straight to the existing `/manage/api/orders/<id>/transition`
/// endpoint (`staff/api.py`), same URL the web queue's own JS calls.
///
/// Models/providers/dialogs are co-located in this file rather than a
/// shared staff models file — Phase 6 was built as several independent
/// screens in parallel (see `staff_models.dart`'s own docstring).
class CashScreen extends ConsumerWidget {
  const CashScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final listAsync = ref.watch(_cashListProvider);
    return StaffScaffold(
      title: 'Cash',
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(_cashListProvider.future),
        child: listAsync.when(
          data: (requests) => _CashBody(requests: requests),
          loading: () => ListView(
            children: const [
              SizedBox(height: 240),
              Center(child: CircularProgressIndicator()),
            ],
          ),
          error: (err, _) => ListView(
            padding: const EdgeInsets.symmetric(horizontal: PosterSpace.pageSidePadding, vertical: 60),
            children: [
              Center(child: Text(_errorText(err), style: PosterText.bodyDefault.copyWith(color: PosterColors.error))),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------- models

class CashRequest {
  const CashRequest({
    required this.id,
    required this.orderNumber,
    required this.customerName,
    required this.totalCents,
    required this.collectionDate,
    required this.slotLabel,
  });

  factory CashRequest.fromJson(Map<String, dynamic> json) => CashRequest(
        id: json['id'] as int,
        orderNumber: json['order_number'] as String,
        customerName: json['customer_name'] as String,
        totalCents: json['total_cents'] as int,
        collectionDate: json['collection_date'] as String,
        slotLabel: json['slot_label'] as String,
      );

  final int id;
  final String orderNumber;
  final String customerName;
  final int totalCents;
  final String collectionDate;
  final String slotLabel;
}

// ---------------------------------------------------------------- provider

final _cashListProvider = FutureProvider<List<CashRequest>>((ref) async {
  final client = ref.watch(apiClientProvider);
  final resp = await client.dio.get<dynamic>('staff/cash/');
  return parseStaffJson(
    resp,
    (d) => ((d as Map<String, dynamic>)['orders'] as List)
        .map((o) => CashRequest.fromJson(o as Map<String, dynamic>))
        .toList(),
  );
});

// ---------------------------------------------------------------- body

class _CashBody extends StatelessWidget {
  const _CashBody({required this.requests});

  final List<CashRequest> requests;

  @override
  Widget build(BuildContext context) {
    if (requests.isEmpty) {
      return ListView(
        children: [
          const SizedBox(height: 200),
          Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: PosterSpace.pageSidePadding),
              child: Text(
                'No cash requests waiting.',
                textAlign: TextAlign.center,
                style: PosterText.bodyLarge.copyWith(color: PosterColors.muted),
              ),
            ),
          ),
        ],
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(
        PosterSpace.pageSidePadding, 16, PosterSpace.pageSidePadding, PosterSpace.bottomPagePadding,
      ),
      itemCount: requests.length,
      itemBuilder: (context, i) => _CashCard(request: requests[i]),
    );
  }
}

class _CashCard extends ConsumerStatefulWidget {
  const _CashCard({required this.request});

  final CashRequest request;

  @override
  ConsumerState<_CashCard> createState() => _CashCardState();
}

class _CashCardState extends ConsumerState<_CashCard> {
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final r = widget.request;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: PosterColors.white,
        border: Border.all(color: PosterColors.border, width: 2),
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(r.orderNumber, style: PosterText.cardTitle.copyWith(fontSize: 18, color: PosterColors.navy)),
              Text(formatCents(r.totalCents), style: PosterText.priceCard.copyWith(fontSize: 18, color: PosterColors.navy)),
            ],
          ),
          const SizedBox(height: 2),
          Text(r.customerName, style: PosterText.bodyLarge.copyWith(color: PosterColors.navy)),
          const SizedBox(height: 4),
          Text(
            '${r.collectionDate} · ${r.slotLabel}',
            style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              FilledButton(
                style: FilledButton.styleFrom(backgroundColor: PosterColors.success),
                onPressed: _busy ? null : _handleAccept,
                child: _busy
                    ? const SizedBox(
                        width: 16, height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2, color: PosterColors.white),
                      )
                    : const Text('Accept'),
              ),
              const SizedBox(width: 8),
              OutlinedButton(
                style: OutlinedButton.styleFrom(
                  foregroundColor: PosterColors.error, side: const BorderSide(color: PosterColors.error),
                ),
                onPressed: _busy ? null : _handleReject,
                child: const Text('Reject'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _handleAccept() async {
    setState(() => _busy = true);
    final ok = await _postTransition(
      context, ref,
      orderId: widget.request.id,
      action: 'accept_cash',
      expectedStatus: 'cash_request',
    );
    if (ok) ref.invalidate(_cashListProvider);
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _handleReject() async {
    final confirmed = await _confirm(
      context,
      title: 'Reject this cash order?',
      message: 'It will be cancelled and the slot freed.',
    );
    if (!confirmed) return;
    if (!mounted) return;
    final reason = await _promptOptionalReason(context);
    if (!mounted) return;
    setState(() => _busy = true);
    final ok = await _postTransition(
      context, ref,
      orderId: widget.request.id,
      action: 'reject_cash',
      expectedStatus: 'cash_request',
      reason: reason,
    );
    if (ok) ref.invalidate(_cashListProvider);
    if (mounted) setState(() => _busy = false);
  }
}

// ---------------------------------------------------------------- dialogs

Future<bool> _confirm(BuildContext context, {required String title, required String message}) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Confirm')),
      ],
    ),
  );
  return result ?? false;
}

/// The reject is already confirmed by the time this shows — "Skip"
/// submits an empty reason (allowed), it never aborts the rejection.
Future<String> _promptOptionalReason(BuildContext context) async {
  final controller = TextEditingController();
  final result = await showDialog<String>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Reason (optional)'),
      content: TextField(
        controller: controller,
        autofocus: true,
        maxLines: 3,
        decoration: const InputDecoration(hintText: 'Optional reason'),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, ''), child: const Text('Skip')),
        FilledButton(onPressed: () => Navigator.pop(ctx, controller.text.trim()), child: const Text('Reject order')),
      ],
    ),
  );
  return result ?? '';
}

// ---------------------------------------------------------------- transition call

/// `POST /manage/api/orders/<id>/transition` — the existing web-queue
/// endpoint (`staff/api.py::transition`), called with the full origin
/// (it lives outside `/api/v1/`, see this module's own header comment).
Future<bool> _postTransition(
  BuildContext context,
  WidgetRef ref, {
  required int orderId,
  required String action,
  required String expectedStatus,
  String? reason,
}) async {
  final client = ref.read(apiClientProvider);
  final uri = Uri.parse(client.dio.options.baseUrl).replace(path: '/manage/api/orders/$orderId/transition');
  try {
    final resp = await client.dio.post<dynamic>(
      uri.toString(),
      data: {
        'action': action,
        'expected_status': expectedStatus,
        'reason': reason,
      },
    );
    parseStaffJson(resp, (d) => d);
    return true;
  } on ApiException catch (e) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
    return false;
  }
}

String _errorText(Object err) => err is ApiException ? err.message : 'Something went wrong.';
