import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api_exception.dart';
import '../../../data/staff/staff_api.dart';
import '../../../state/api_providers.dart';
import '../../../theme/poster_tokens.dart';
import '../staff_scaffold.dart';

/// Collection board (§12.5) — spec-driven mobile port of `staff/
/// templates/staff/collection.html` + `static/js/collection.js`.
/// Backend: `GET /api/v1/staff/collection/?date=`
/// (`staff/api_mobile_collection_cash.py::collection_json`). Row actions
/// (`mark_ready`/`mark_collected`/`uncollect`/`close_out_no_show`) and
/// the day-level "Close out day" button POST straight to the existing
/// `/manage/api/orders/<id>/transition` and
/// `/manage/api/days/<date>/close-out` endpoints (`staff/api.py`), same
/// URLs the web board's own JS calls.
///
/// Models/providers/dialogs are co-located in this file rather than a
/// shared staff models file — Phase 6 was built as several independent
/// screens in parallel (see `staff_models.dart`'s own docstring).
class StaffCollectionScreen extends ConsumerWidget {
  const StaffCollectionScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dateIso = ref.watch(_collectionDateProvider);
    final dataAsync = ref.watch(_collectionProvider(dateIso));

    return StaffScaffold(
      title: 'Collection',
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(_collectionProvider(dateIso).future),
        child: dataAsync.when(
          data: (data) => _CollectionBody(data: data, dateIso: dateIso),
          loading: () => ListView(
            children: const [
              SizedBox(height: 240),
              Center(child: CircularProgressIndicator()),
            ],
          ),
          error: (err, _) => ListView(
            padding: const EdgeInsets.symmetric(horizontal: PosterSpace.pageSidePadding, vertical: 24),
            children: [
              _DateHeader(dateIso: dateIso),
              const SizedBox(height: 60),
              Center(child: Text(_errorText(err), style: PosterText.bodyDefault.copyWith(color: PosterColors.error))),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------- models

class CollectionTicket {
  const CollectionTicket({
    required this.id,
    required this.orderNumber,
    required this.customerName,
    required this.itemCount,
    required this.paymentMethod,
    required this.cashAmountDisplay,
    required this.isPaid,
    required this.status,
  });

  factory CollectionTicket.fromJson(Map<String, dynamic> json) => CollectionTicket(
        id: json['id'] as int,
        orderNumber: json['order_number'] as String,
        customerName: json['customer_name'] as String,
        itemCount: json['item_count'] as int,
        paymentMethod: json['payment_method'] as String,
        cashAmountDisplay: json['cash_amount_display'] as String?,
        isPaid: json['is_paid'] as bool,
        status: json['status'] as String,
      );

  final int id;
  final String orderNumber;
  final String customerName;
  final int itemCount;
  final String paymentMethod; // "eft" | "cash"
  final String? cashAmountDisplay;
  final bool isPaid;
  final String status; // "in_kitchen" | "ready" | "collected"

  bool get isCash => paymentMethod == 'cash';
}

class CollectionSlotGroup {
  const CollectionSlotGroup({
    required this.slotId,
    required this.startAt,
    required this.endAt,
    required this.isNow,
    required this.tickets,
  });

  factory CollectionSlotGroup.fromJson(Map<String, dynamic> json) => CollectionSlotGroup(
        slotId: json['slot_id'] as int,
        startAt: json['start_at'] as String,
        endAt: json['end_at'] as String,
        isNow: json['is_now'] as bool,
        tickets: (json['tickets'] as List)
            .map((t) => CollectionTicket.fromJson(t as Map<String, dynamic>))
            .toList(),
      );

  final int slotId;
  final String startAt;
  final String endAt;
  final bool isNow;
  final List<CollectionTicket> tickets;
}

class CollectionData {
  const CollectionData({
    required this.date,
    required this.slots,
    required this.uncollected,
    required this.canCloseOut,
  });

  factory CollectionData.fromJson(Map<String, dynamic> json) => CollectionData(
        date: json['date'] as String,
        slots: (json['slots'] as List)
            .map((s) => CollectionSlotGroup.fromJson(s as Map<String, dynamic>))
            .toList(),
        uncollected: (json['uncollected'] as List)
            .map((t) => CollectionTicket.fromJson(t as Map<String, dynamic>))
            .toList(),
        canCloseOut: json['can_close_out'] as bool,
      );

  final String date;
  final List<CollectionSlotGroup> slots;
  final List<CollectionTicket> uncollected;
  final bool canCloseOut;
}

// ---------------------------------------------------------------- providers

/// Selected board date (ISO `yyyy-MM-dd`), local to this screen — prev/
/// next day arrows write to it, `_collectionProvider` reads it as its
/// family key so each date gets its own cached fetch.
final _collectionDateProvider = StateProvider<String>((ref) => _isoDate(DateTime.now()));

final _collectionProvider = FutureProvider.family<CollectionData, String>((ref, dateIso) async {
  final client = ref.watch(apiClientProvider);
  final resp = await client.dio.get<dynamic>('staff/collection/', queryParameters: {'date': dateIso});
  return parseStaffJson(resp, (d) => CollectionData.fromJson(d as Map<String, dynamic>));
});

// ---------------------------------------------------------------- body

class _CollectionBody extends StatelessWidget {
  const _CollectionBody({required this.data, required this.dateIso});

  final CollectionData data;
  final String dateIso;

  @override
  Widget build(BuildContext context) {
    final hasAnything = data.slots.isNotEmpty || data.uncollected.isNotEmpty;
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        PosterSpace.pageSidePadding, 16, PosterSpace.pageSidePadding, PosterSpace.bottomPagePadding,
      ),
      children: [
        _DateHeader(dateIso: dateIso),
        const SizedBox(height: 12),
        if (!hasAnything)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 32),
            child: Text(
              'Nothing on the collection board yet. Orders appear here once they '
              'are ready for collection or in the kitchen.',
              style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
            ),
          ),
        for (final group in data.slots) _SlotSection(group: group, dateIso: dateIso),
        if (data.uncollected.isNotEmpty) _UncollectedSection(tickets: data.uncollected, dateIso: dateIso),
        if (data.canCloseOut) _CloseOutSection(uncollectedCount: data.uncollected.length, dateIso: dateIso),
      ],
    );
  }
}

class _DateHeader extends ConsumerWidget {
  const _DateHeader({required this.dateIso});

  final String dateIso;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final date = DateTime.parse(dateIso);
    final isToday = _isoDate(DateTime.now()) == dateIso;
    return Row(
      children: [
        IconButton(
          onPressed: () => ref.read(_collectionDateProvider.notifier).state =
              _isoDate(date.subtract(const Duration(days: 1))),
          icon: const Icon(Icons.chevron_left_rounded, color: PosterColors.navy),
        ),
        Expanded(
          child: Text(
            '${isToday ? 'Today, ' : ''}${_formatDateLabel(date)}',
            textAlign: TextAlign.center,
            style: PosterText.cardTitle.copyWith(fontSize: 18, color: PosterColors.navy),
          ),
        ),
        IconButton(
          onPressed: () => ref.read(_collectionDateProvider.notifier).state =
              _isoDate(date.add(const Duration(days: 1))),
          icon: const Icon(Icons.chevron_right_rounded, color: PosterColors.navy),
        ),
      ],
    );
  }
}

class _SlotSection extends StatelessWidget {
  const _SlotSection({required this.group, required this.dateIso});

  final CollectionSlotGroup group;
  final String dateIso;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                '${group.startAt}–${group.endAt}',
                style: PosterText.cardTitle.copyWith(
                  fontSize: 16,
                  color: group.isNow ? PosterColors.blue : PosterColors.navy,
                ),
              ),
              if (group.isNow) ...[
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(color: PosterColors.blue, borderRadius: BorderRadius.circular(3)),
                  child: const Text('NOW', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w900, color: PosterColors.white)),
                ),
              ],
            ],
          ),
          const Divider(color: PosterColors.border, height: 16),
          for (final ticket in group.tickets) _TicketCard(ticket: ticket, dateIso: dateIso),
        ],
      ),
    );
  }
}

class _UncollectedSection extends StatelessWidget {
  const _UncollectedSection({required this.tickets, required this.dateIso});

  final List<CollectionTicket> tickets;
  final String dateIso;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('UNCOLLECTED', style: PosterText.eyebrow.copyWith(color: PosterColors.error)),
          const SizedBox(height: 4),
          Text(
            'Past the collection window and not picked up. Use No-show to close '
            'each one, or contact the customer first.',
            style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
          ),
          const Divider(color: PosterColors.border, height: 16),
          for (final ticket in tickets) _UncollectedCard(ticket: ticket, dateIso: dateIso),
        ],
      ),
    );
  }
}

class _UncollectedCard extends ConsumerStatefulWidget {
  const _UncollectedCard({required this.ticket, required this.dateIso});

  final CollectionTicket ticket;
  final String dateIso;

  @override
  ConsumerState<_UncollectedCard> createState() => _UncollectedCardState();
}

class _UncollectedCardState extends ConsumerState<_UncollectedCard> {
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final ticket = widget.ticket;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: PosterColors.white,
        border: Border.all(color: PosterColors.error, width: 2),
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(ticket.orderNumber, style: PosterText.cardTitle.copyWith(fontSize: 16, color: PosterColors.navy)),
                Text(ticket.customerName, style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
              ],
            ),
          ),
          const SizedBox(width: 8),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: PosterColors.error),
            onPressed: _busy ? null : _handleNoShow,
            child: _busy
                ? const SizedBox(
                    width: 16, height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2, color: PosterColors.white),
                  )
                : const Text('No-show'),
          ),
        ],
      ),
    );
  }

  Future<void> _handleNoShow() async {
    final confirmed = await _confirm(
      context,
      title: 'Mark this order as a no-show?',
      message: 'This cannot be undone.',
    );
    if (!confirmed) return;
    if (!mounted) return;
    setState(() => _busy = true);
    final ok = await _postTransition(
      context, ref,
      orderId: widget.ticket.id,
      action: 'close_out_no_show',
      expectedStatus: widget.ticket.status,
    );
    if (ok) ref.invalidate(_collectionProvider(widget.dateIso));
    if (mounted) setState(() => _busy = false);
  }
}

class _CloseOutSection extends ConsumerStatefulWidget {
  const _CloseOutSection({required this.uncollectedCount, required this.dateIso});

  final int uncollectedCount;
  final String dateIso;

  @override
  ConsumerState<_CloseOutSection> createState() => _CloseOutSectionState();
}

class _CloseOutSectionState extends ConsumerState<_CloseOutSection> {
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final count = widget.uncollectedCount;
    return Container(
      margin: const EdgeInsets.only(top: 24),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PosterColors.white,
        border: Border.all(color: PosterColors.gold, width: 2),
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Close out day', style: PosterText.cardTitle.copyWith(fontSize: 16, color: PosterColors.navy)),
          const SizedBox(height: 6),
          Text(
            count > 0
                ? 'The collection window plus grace period has passed. Closing out will '
                    'mark the $count remaining order${count == 1 ? '' : 's'} as no-shows. '
                    'This cannot be undone.'
                : 'The collection window plus grace period has passed. No orders are '
                    'left to close out.',
            style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
          ),
          const SizedBox(height: 12),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: PosterColors.navy),
            onPressed: _busy ? null : _handleCloseOut,
            child: _busy
                ? const SizedBox(
                    width: 16, height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2, color: PosterColors.white),
                  )
                : const Text('Close out day'),
          ),
        ],
      ),
    );
  }

  Future<void> _handleCloseOut() async {
    final count = widget.uncollectedCount;
    final confirmed = await _confirm(
      context,
      title: 'Close out the day?',
      message: count > 0
          ? 'This will mark $count order${count == 1 ? '' : 's'} as no-shows and cannot be undone.'
          : 'No orders are left to close out.',
    );
    if (!confirmed) return;
    if (!mounted) return;
    setState(() => _busy = true);
    final ok = await _postCloseOutDay(context, ref, widget.dateIso);
    if (ok) ref.invalidate(_collectionProvider(widget.dateIso));
    if (mounted) setState(() => _busy = false);
  }
}

class _TicketCard extends StatelessWidget {
  const _TicketCard({required this.ticket, required this.dateIso});

  final CollectionTicket ticket;
  final String dateIso;

  @override
  Widget build(BuildContext context) {
    final opacity = ticket.status == 'in_kitchen'
        ? 0.55
        : ticket.status == 'collected'
            ? 0.4
            : 1.0;
    return Opacity(
      opacity: opacity,
      child: Container(
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
                Text(ticket.orderNumber, style: PosterText.cardTitle.copyWith(fontSize: 18, color: PosterColors.navy)),
                _StatusTag(status: ticket.status),
              ],
            ),
            const SizedBox(height: 2),
            Text(ticket.customerName, style: PosterText.bodyLarge.copyWith(color: PosterColors.navy)),
            const SizedBox(height: 4),
            Wrap(
              spacing: 10,
              runSpacing: 4,
              children: [
                Text(
                  '${ticket.itemCount} item${ticket.itemCount == 1 ? '' : 's'}',
                  style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
                ),
                if (ticket.isCash)
                  Text(
                    'CASH ${ticket.cashAmountDisplay ?? ''}',
                    style: PosterText.bodyDefault.copyWith(color: PosterColors.blue, fontWeight: FontWeight.w800),
                  )
                else if (ticket.isPaid)
                  Text('PAID', style: PosterText.bodyDefault.copyWith(color: PosterColors.success, fontWeight: FontWeight.w800)),
              ],
            ),
            const SizedBox(height: 10),
            _TicketActions(ticket: ticket, dateIso: dateIso),
          ],
        ),
      ),
    );
  }
}

class _StatusTag extends StatelessWidget {
  const _StatusTag({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final String label;
    final Color color;
    switch (status) {
      case 'ready':
        label = 'READY';
        color = PosterColors.success;
        break;
      case 'in_kitchen':
        label = 'NOT READY';
        color = PosterColors.muted;
        break;
      case 'collected':
        label = 'COLLECTED';
        color = PosterColors.muted;
        break;
      default:
        label = status.toUpperCase();
        color = PosterColors.muted;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3)),
      child: Text(label, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w900, color: PosterColors.white)),
    );
  }
}

class _TicketActions extends ConsumerStatefulWidget {
  const _TicketActions({required this.ticket, required this.dateIso});

  final CollectionTicket ticket;
  final String dateIso;

  @override
  ConsumerState<_TicketActions> createState() => _TicketActionsState();
}

class _TicketActionsState extends ConsumerState<_TicketActions> {
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final ticket = widget.ticket;
    Widget button;
    switch (ticket.status) {
      case 'in_kitchen':
        button = _actionButton('Mark ready', _handleMarkReady);
        break;
      case 'ready':
        button = _actionButton('Collected', _handleMarkCollected);
        break;
      case 'collected':
        button = _actionButton('Uncollect', _handleUncollect, outlined: true);
        break;
      default:
        button = const SizedBox.shrink();
    }
    return Align(alignment: Alignment.centerLeft, child: button);
  }

  Widget _actionButton(String label, VoidCallback onPressed, {bool outlined = false}) {
    final child = _busy
        ? SizedBox(
            width: 16, height: 16,
            child: CircularProgressIndicator(
              strokeWidth: 2, color: outlined ? PosterColors.navy : PosterColors.white,
            ),
          )
        : Text(label);
    if (outlined) {
      return OutlinedButton(
        style: OutlinedButton.styleFrom(foregroundColor: PosterColors.navy, side: const BorderSide(color: PosterColors.navy)),
        onPressed: _busy ? null : onPressed,
        child: child,
      );
    }
    return FilledButton(
      style: FilledButton.styleFrom(backgroundColor: PosterColors.navy),
      onPressed: _busy ? null : onPressed,
      child: child,
    );
  }

  Future<void> _handleMarkReady() async {
    await _run(() => _postTransition(
          context, ref,
          orderId: widget.ticket.id,
          action: 'mark_ready',
          expectedStatus: 'in_kitchen',
        ));
  }

  Future<void> _handleMarkCollected() async {
    Map<String, dynamic>? payload;
    if (widget.ticket.isCash) {
      final prefill = (widget.ticket.cashAmountDisplay ?? '').replaceFirst('R', '').trim();
      final cents = await _promptCashAmount(context, prefill);
      if (cents == null) return; // cancelled, or an invalid amount was entered
      payload = {'cash_amount_received_cents': cents};
    }
    await _run(() => _postTransition(
          context, ref,
          orderId: widget.ticket.id,
          action: 'mark_collected',
          expectedStatus: 'ready',
          payload: payload,
        ));
  }

  Future<void> _handleUncollect() async {
    final reason = await _promptReason(context, title: 'Reason for uncollecting (required)');
    if (reason == null) return;
    await _run(() => _postTransition(
          context, ref,
          orderId: widget.ticket.id,
          action: 'uncollect',
          expectedStatus: 'collected',
          reason: reason,
        ));
  }

  Future<void> _run(Future<bool> Function() action) async {
    setState(() => _busy = true);
    final ok = await action();
    if (ok) ref.invalidate(_collectionProvider(widget.dateIso));
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

Future<String?> _promptReason(BuildContext context, {required String title}) async {
  final controller = TextEditingController();
  final result = await showDialog<String>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: TextField(controller: controller, autofocus: true, maxLines: 3, decoration: const InputDecoration(hintText: 'Reason')),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(ctx, controller.text.trim()), child: const Text('Confirm')),
      ],
    ),
  );
  if (result == null || result.isEmpty) return null;
  return result;
}

Future<int?> _promptCashAmount(BuildContext context, String prefillRands) async {
  final controller = TextEditingController(text: prefillRands);
  final result = await showDialog<String>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Cash amount received (R)'),
      content: TextField(
        controller: controller,
        autofocus: true,
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        decoration: const InputDecoration(prefixText: 'R '),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(ctx, controller.text.trim()), child: const Text('Confirm')),
      ],
    ),
  );
  if (result == null) return null; // cancelled
  final rands = double.tryParse(result);
  if (rands == null || rands < 0) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Enter a valid amount.')));
    }
    return null;
  }
  return (rands * 100).round();
}

// ---------------------------------------------------------------- transition calls

/// `POST /manage/api/orders/<id>/transition` — the existing web-board
/// endpoint (`staff/api.py::transition`), called with the full origin
/// (it lives outside `/api/v1/`, see this module's own header comment).
Future<bool> _postTransition(
  BuildContext context,
  WidgetRef ref, {
  required int orderId,
  required String action,
  required String expectedStatus,
  String? reason,
  Map<String, dynamic>? payload,
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
        'payload': payload ?? <String, dynamic>{},
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

/// `POST /manage/api/days/<date>/close-out` (`staff/api.py::close_out_day`).
Future<bool> _postCloseOutDay(BuildContext context, WidgetRef ref, String dateIso) async {
  final client = ref.read(apiClientProvider);
  final uri = Uri.parse(client.dio.options.baseUrl).replace(path: '/manage/api/days/$dateIso/close-out');
  try {
    final resp = await client.dio.post<dynamic>(uri.toString());
    parseStaffJson(resp, (d) => d);
    return true;
  } on ApiException catch (e) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
    return false;
  }
}

// ---------------------------------------------------------------- date helpers

const _dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const _monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

String _isoDate(DateTime date) => date.toIso8601String().substring(0, 10);

String _formatDateLabel(DateTime date) => '${_dayNames[date.weekday - 1]} ${date.day} ${_monthNames[date.month - 1]}';

String _errorText(Object err) => err is ApiException ? err.message : 'Something went wrong.';
