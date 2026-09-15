import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api_exception.dart';
import '../../../data/staff/staff_api.dart';
import '../../../state/api_providers.dart';
import '../../../theme/poster_tokens.dart';
import '../../../util/money.dart';
import '../staff_scaffold.dart';

/// Payments — the EFT queue (`GET /api/v1/staff/payments/`,
/// `staff/api_mobile_payments.py::payments_json`). Web reference:
/// `staff/views.py::payments_queue` / `templates/staff/payments.html` /
/// `static/js/payments.js`. Row actions POST straight to the existing
/// `manage:api_transition` endpoint (`/manage/api/orders/<id>/transition`)
/// — not under `/api/v1/staff/` — same URL the web board's own JS calls.

class PaymentRow {
  const PaymentRow({
    required this.id,
    required this.orderNumber,
    required this.customerName,
    required this.totalCents,
    required this.slotWindow,
    required this.holdExpiresAt,
    required this.proofUploaded,
    required this.status,
  });

  factory PaymentRow.fromJson(Map<String, dynamic> json) => PaymentRow(
        id: json['id'] as int,
        orderNumber: json['order_number'] as String,
        customerName: json['customer_name'] as String,
        totalCents: json['total_cents'] as int,
        slotWindow: json['slot_window'] as String?,
        holdExpiresAt: json['hold_expires_at'] == null
            ? null
            : DateTime.parse(json['hold_expires_at'] as String),
        proofUploaded: json['proof_uploaded'] as bool,
        status: json['status'] as String,
      );

  final int id;
  final String orderNumber;
  final String customerName;
  final int totalCents;
  final String? slotWindow;
  final DateTime? holdExpiresAt;
  final bool proofUploaded;
  final String status; // "awaiting_eft" | "payment_review"
}

class PaymentsQueue {
  const PaymentsQueue({required this.rows, required this.holdExtensionMinutes});

  factory PaymentsQueue.fromJson(Map<String, dynamic> json) => PaymentsQueue(
        rows: (json['rows'] as List<dynamic>)
            .map((e) => PaymentRow.fromJson(e as Map<String, dynamic>))
            .toList(),
        holdExtensionMinutes: json['hold_extension_minutes'] as int,
      );

  final List<PaymentRow> rows;
  final int holdExtensionMinutes;
}

final paymentsQueueProvider = FutureProvider.autoDispose<PaymentsQueue>((ref) async {
  final resp = await ref.watch(apiClientProvider).dio.get<dynamic>('staff/payments/');
  return parseStaffJson(resp, (d) => PaymentsQueue.fromJson(d as Map<String, dynamic>));
});

/// The action endpoint lives at `/manage/api/orders/<id>/transition` —
/// the *origin*, not `/api/v1/staff/...` (see this screen's own
/// docstring / AGENTS.md's shared-conventions note).
Future<void> _postTransition(
  WidgetRef ref, {
  required int orderId,
  required String action,
  required String expectedStatus,
  String? reason,
}) async {
  final dio = ref.read(apiClientProvider).dio;
  final origin = Uri.parse(dio.options.baseUrl).replace(path: '/manage/api/orders/$orderId/transition');
  final resp = await dio.postUri<dynamic>(
    origin,
    data: {'action': action, 'expected_status': expectedStatus, 'reason': ?reason},
  );
  final status = resp.statusCode ?? 0;
  if (status >= 200 && status < 300) return;
  final data = resp.data;
  var message = 'That didn\'t work — try again.';
  String? code;
  if (data is Map<String, dynamic>) {
    code = data['error'] as String?;
    message = (data['message'] as String?) ?? message;
  }
  if (status == 409) message = '$message Reload the page to see the current state.';
  throw ApiException(code: code ?? 'unknown', message: message, statusCode: status);
}

class PaymentsScreen extends ConsumerWidget {
  const PaymentsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final queueAsync = ref.watch(paymentsQueueProvider);

    return StaffScaffold(
      title: 'Payments',
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(paymentsQueueProvider.future),
        child: queueAsync.when(
          data: (queue) => queue.rows.isEmpty
              ? ListView(
                  padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
                  children: const [
                    SizedBox(height: 80),
                    Center(
                      child: Text(
                        'Nothing awaiting EFT payment or verification right now.',
                        style: PosterText.bodyLarge,
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],
                )
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(
                    PosterSpace.pageSidePadding, 12, PosterSpace.pageSidePadding, PosterSpace.bottomPagePadding,
                  ),
                  itemCount: queue.rows.length,
                  separatorBuilder: (context, i) => const SizedBox(height: 12),
                  itemBuilder: (context, i) => _PaymentCard(
                    row: queue.rows[i],
                    holdExtensionMinutes: queue.holdExtensionMinutes,
                  ),
                ),
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (err, _) => ListView(
            padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
            children: [
              const SizedBox(height: 80),
              Center(
                child: Text(
                  err is ApiException ? err.message : '$err',
                  style: PosterText.bodyDefault.copyWith(color: PosterColors.error),
                  textAlign: TextAlign.center,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PaymentCard extends ConsumerStatefulWidget {
  const _PaymentCard({required this.row, required this.holdExtensionMinutes});

  final PaymentRow row;
  final int holdExtensionMinutes;

  @override
  ConsumerState<_PaymentCard> createState() => _PaymentCardState();
}

class _PaymentCardState extends ConsumerState<_PaymentCard> {
  Timer? _ticker;
  Duration? _remaining;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _updateRemaining();
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) => _updateRemaining());
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  void _updateRemaining() {
    final holdExpiresAt = widget.row.holdExpiresAt;
    if (holdExpiresAt == null) {
      if (mounted) setState(() => _remaining = null);
      return;
    }
    final diff = holdExpiresAt.difference(DateTime.now());
    if (mounted) setState(() => _remaining = diff);
  }

  Future<void> _runAction({
    required String action,
    required String label,
    bool needsReason = false,
  }) async {
    String? reason;
    if (needsReason) {
      reason = await _promptForReason(context, label);
      if (reason == null || reason.trim().isEmpty) return; // cancelled or blank
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await _postTransition(
        ref,
        orderId: widget.row.id,
        action: action,
        expectedStatus: widget.row.status,
        reason: reason,
      );
      ref.invalidate(paymentsQueueProvider);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) setState(() => _error = "Couldn't reach the server — check your connection and try again.");
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<String?> _promptForReason(BuildContext context, String actionLabel) {
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('$actionLabel — reason required'),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLines: 3,
          decoration: const InputDecoration(hintText: 'Reason'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(controller.text.trim()),
            child: const Text('Confirm'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final row = widget.row;
    final remaining = _remaining;
    final lapsed = remaining != null && remaining.isNegative;

    return Container(
      decoration: BoxDecoration(
        color: PosterColors.white,
        border: Border.all(color: PosterColors.border, width: 2),
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      ),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  '${row.orderNumber} — ${row.customerName}',
                  style: PosterText.cardTitle.copyWith(fontSize: 16, color: PosterColors.navy),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Text(formatCents(row.totalCents), style: PosterText.priceCard.copyWith(fontSize: 18, color: PosterColors.navy)),
            ],
          ),
          const SizedBox(height: 4),
          Wrap(
            spacing: 12,
            runSpacing: 4,
            children: [
              if (row.slotWindow != null)
                Text(row.slotWindow!, style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
              Text(
                row.proofUploaded ? 'Proof: Uploaded' : 'Proof: —',
                style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
              ),
              Text(
                row.status == 'payment_review' ? 'Payment review' : 'Awaiting EFT',
                style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            remaining == null
                ? 'No hold deadline'
                : lapsed
                    ? 'Lapsed — hold expired'
                    : '${_formatDuration(remaining)} remaining',
            style: PosterText.bodyDefault.copyWith(
              color: lapsed ? PosterColors.error : PosterColors.navy,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (row.status == 'payment_review') ...[
                _ActionButton(
                  label: 'Verify',
                  busy: _busy,
                  onPressed: () => _runAction(action: 'verify_eft', label: 'Verify'),
                ),
                _ActionButton(
                  label: 'Reject',
                  busy: _busy,
                  destructive: true,
                  onPressed: () => _runAction(action: 'reject_eft', label: 'Reject', needsReason: true),
                ),
              ],
              if (row.status == 'awaiting_eft') ...[
                _ActionButton(
                  label: 'Verify (seen in bank app)',
                  busy: _busy,
                  onPressed: () => _runAction(action: 'verify_eft', label: 'Verify', needsReason: true),
                ),
                _ActionButton(
                  label: 'Expire now',
                  busy: _busy,
                  destructive: true,
                  onPressed: () => _runAction(action: 'expire_hold_now', label: 'Expire now'),
                ),
              ],
              _ActionButton(
                label: 'Extend hold (+${widget.holdExtensionMinutes}m)',
                busy: _busy,
                onPressed: () => _runAction(action: 'extend_hold', label: 'Extend hold'),
              ),
            ],
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: PosterText.bodyDefault.copyWith(color: PosterColors.error)),
          ],
        ],
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.label,
    required this.onPressed,
    required this.busy,
    this.destructive = false,
  });

  final String label;
  final VoidCallback onPressed;
  final bool busy;
  final bool destructive;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton(
      onPressed: busy ? null : onPressed,
      style: OutlinedButton.styleFrom(
        foregroundColor: destructive ? PosterColors.error : PosterColors.navy,
        side: BorderSide(color: destructive ? PosterColors.error : PosterColors.navy),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(PosterSpace.radiusButton)),
      ),
      child: Text(label, style: PosterText.bodyDefault.copyWith(fontWeight: FontWeight.w800)),
    );
  }
}

String _formatDuration(Duration d) {
  final minutes = d.inMinutes;
  final seconds = d.inSeconds % 60;
  return '${minutes}m ${seconds}s';
}
