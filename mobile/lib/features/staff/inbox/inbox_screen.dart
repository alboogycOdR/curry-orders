import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../data/api_exception.dart';
import '../../../data/staff/staff_api.dart';
import '../../../state/api_providers.dart';
import '../../../state/staff_auth.dart';
import '../../../theme/poster_tokens.dart';
import '../staff_scaffold.dart';

/// Inbox — the staff landing page (§12.2). Backend:
/// `GET /api/v1/staff/inbox/` (`staff/api_mobile_boards.py::inbox_json`).
/// Five sections (cash requests, hold-lapsed/SLA-breached, orders with
/// notes, recent assisted, recently expired), each a group of order
/// rows with its own row actions. Row actions POST straight to the
/// existing web action endpoints (`/manage/api/orders/:id/transition`,
/// `/manage/api/orders/:id/assign`) — not under `/api/v1/` — then
/// refetch the whole inbox rather than locally mutating state, so the
/// six sections never drift out of sync with each other after an
/// action moves an order between them.
///
/// Models/providers are kept local to this file rather than a shared
/// `staff/inbox/` provider file — Phase 6 was built as several
/// independent screens in parallel (see `data/staff/staff_models.dart`'s
/// own docstring for the same reasoning).
class InboxScreen extends ConsumerStatefulWidget {
  const InboxScreen({super.key});

  @override
  ConsumerState<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends ConsumerState<InboxScreen> {
  late Future<InboxData> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<InboxData> _load() async {
    final dio = ref.read(apiClientProvider).dio;
    final resp = await dio.get<dynamic>('staff/inbox/');
    return parseStaffJson(resp, (d) => InboxData.fromJson(d as Map<String, dynamic>));
  }

  Future<void> _refresh() async {
    final next = _load();
    setState(() => _future = next);
    await next;
  }

  @override
  Widget build(BuildContext context) {
    return StaffScaffold(
      title: 'Inbox',
      body: FutureBuilder<InboxData>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _ScrollableMessage(
              onRefresh: _refresh,
              message: snapshot.error is ApiException
                  ? (snapshot.error! as ApiException).message
                  : 'Could not load the inbox.',
            );
          }
          final data = snapshot.data!;
          if (data.isEmpty) {
            return _ScrollableMessage(onRefresh: _refresh, message: 'Inbox is clear.', isGood: true);
          }
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(
                PosterSpace.pageSidePadding, 16, PosterSpace.pageSidePadding, PosterSpace.bottomPagePadding,
              ),
              children: [
                _Section(
                  title: 'Cash requests',
                  rows: data.cashRequests,
                  showCashActions: true,
                  onChanged: _refresh,
                ),
                _Section(
                  title: 'Hold lapsed / SLA breached',
                  rows: data.holdLapsed,
                  onChanged: _refresh,
                ),
                _Section(
                  title: 'Orders with notes',
                  rows: data.ordersWithNotes,
                  onChanged: _refresh,
                ),
                _Section(
                  title: 'Recent assisted',
                  rows: data.recentAssisted,
                  onChanged: _refresh,
                ),
                _Section(
                  title: 'Recently expired',
                  rows: data.recentlyExpired,
                  showReinstate: true,
                  onChanged: _refresh,
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _ScrollableMessage extends StatelessWidget {
  const _ScrollableMessage({required this.onRefresh, required this.message, this.isGood = false});

  final Future<void> Function() onRefresh;
  final String message;
  final bool isGood;

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: onRefresh,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(32),
        children: [
          const SizedBox(height: 120),
          Icon(
            isGood ? Icons.check_circle_outline_rounded : Icons.error_outline_rounded,
            color: isGood ? PosterColors.success : PosterColors.error,
            size: 40,
          ),
          const SizedBox(height: 12),
          Text(message, textAlign: TextAlign.center, style: PosterText.bodyLarge.copyWith(color: PosterColors.navy)),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({
    required this.title,
    required this.rows,
    required this.onChanged,
    this.showCashActions = false,
    this.showReinstate = false,
  });

  final String title;
  final List<InboxRow> rows;
  final bool showCashActions;
  final bool showReinstate;
  final Future<void> Function() onChanged;

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          initiallyExpanded: true,
          tilePadding: EdgeInsets.zero,
          childrenPadding: EdgeInsets.zero,
          title: Row(
            children: [
              Expanded(
                child: Text(
                  title.toUpperCase(),
                  style: PosterText.eyebrow.copyWith(color: PosterColors.navy),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: PosterColors.bluePanel,
                  borderRadius: BorderRadius.circular(PosterSpace.radiusButton),
                ),
                child: Text(
                  '${rows.length}',
                  style: PosterText.bodyDefault.copyWith(color: PosterColors.white, fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
          children: [
            for (final row in rows)
              _InboxRowCard(
                row: row,
                showCashActions: showCashActions,
                showReinstate: showReinstate,
                onChanged: onChanged,
              ),
          ],
        ),
      ),
    );
  }
}

class _InboxRowCard extends ConsumerStatefulWidget {
  const _InboxRowCard({
    required this.row,
    required this.showCashActions,
    required this.showReinstate,
    required this.onChanged,
  });

  final InboxRow row;
  final bool showCashActions;
  final bool showReinstate;
  final Future<void> Function() onChanged;

  @override
  ConsumerState<_InboxRowCard> createState() => _InboxRowCardState();
}

class _InboxRowCardState extends ConsumerState<_InboxRowCard> {
  bool _busy = false;

  Future<void> _run(Future<void> Function(Dio dio) call) async {
    if (_busy) return;
    setState(() => _busy = true);
    final dio = ref.read(apiClientProvider).dio;
    try {
      await call(dio);
      await widget.onChanged();
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message), backgroundColor: PosterColors.error),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _assign() => _run((dio) => _staffAssign(dio, orderId: widget.row.id));

  Future<void> _transition(String action, {String? reason}) => _run(
        (dio) => _staffTransition(
          dio,
          orderId: widget.row.id,
          action: action,
          expectedStatus: widget.row.status,
          reason: reason,
        ),
      );

  Future<void> _reinstate() async {
    final reason = await _promptReason(context, title: 'Reinstate order', hint: 'Why is this being reinstated?');
    if (reason == null) return;
    await _transition('reinstate', reason: reason);
  }

  @override
  Widget build(BuildContext context) {
    final row = widget.row;
    final user = ref.watch(staffAuthProvider).user;
    final assignedToMe = user != null && row.assignedUserName == user.name;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: PosterColors.white,
        border: Border.all(color: PosterColors.border, width: 1.5),
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(row.orderNumber, style: PosterText.cardTitle.copyWith(fontSize: 16, color: PosterColors.navy)),
              ),
              Text(row.status.replaceAll('_', ' ').toUpperCase(), style: PosterText.bodyDefault.copyWith(color: PosterColors.blue)),
            ],
          ),
          const SizedBox(height: 4),
          Text(row.customerName, style: PosterText.bodyLarge.copyWith(color: PosterColors.navy)),
          if (row.slotLabel != null || row.collectionDate != null)
            Text(
              [?row.collectionDate, ?row.slotLabel].join(' · '),
              style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
            ),
          if (row.note != null && row.note!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('"${row.note}"', style: PosterText.bodyDefault.copyWith(color: PosterColors.muted, fontStyle: FontStyle.italic)),
            ),
          const SizedBox(height: 4),
          Text(
            row.assignedUserName != null ? 'Assigned: ${row.assignedUserName}' : 'Unassigned',
            style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (row.customerMobileE164 != null)
                OutlinedButton.icon(
                  onPressed: () => _contact(row.customerMobileE164!, row.customerName, row.orderNumber),
                  icon: const Icon(Icons.chat_rounded, size: 16),
                  label: const Text('WhatsApp'),
                ),
              OutlinedButton(
                onPressed: _busy ? null : _assign,
                child: Text(assignedToMe ? 'Unassign' : 'Assign to me'),
              ),
              if (widget.showCashActions) ...[
                FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: PosterColors.success),
                  onPressed: _busy ? null : () => _transition('accept_cash'),
                  child: const Text('Accept'),
                ),
                FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: PosterColors.error),
                  onPressed: _busy ? null : () => _transition('reject_cash'),
                  child: const Text('Reject'),
                ),
              ],
              if (widget.showReinstate)
                FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: PosterColors.gold, foregroundColor: PosterColors.navy),
                  onPressed: _busy ? null : _reinstate,
                  child: const Text('Reinstate'),
                ),
              if (_busy) const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2)),
            ],
          ),
        ],
      ),
    );
  }
}

Future<void> _contact(String mobileE164, String customerName, String orderNumber) async {
  final digits = mobileE164.replaceAll('+', '');
  final text = Uri.encodeComponent('Hi $customerName, about order $orderNumber');
  final uri = Uri.parse('https://wa.me/$digits?text=$text');
  await launchUrl(uri, mode: LaunchMode.externalApplication);
}

Future<String?> _promptReason(BuildContext context, {required String title, String? hint}) {
  final controller = TextEditingController();
  return showDialog<String>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: TextField(
        controller: controller,
        autofocus: true,
        maxLines: 3,
        decoration: InputDecoration(hintText: hint, border: const OutlineInputBorder()),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Cancel')),
        FilledButton(
          onPressed: () {
            final text = controller.text.trim();
            if (text.isEmpty) return;
            Navigator.of(ctx).pop(text);
          },
          child: const Text('Confirm'),
        ),
      ],
    ),
  );
}

// ---------------------------------------------------------------- models

class InboxRow {
  const InboxRow({
    required this.id,
    required this.orderNumber,
    required this.publicToken,
    required this.customerName,
    required this.customerMobileE164,
    required this.collectionDate,
    required this.slotLabel,
    required this.status,
    required this.note,
    required this.assignedUserName,
  });

  factory InboxRow.fromJson(Map<String, dynamic> json) => InboxRow(
        id: json['id'] as int,
        orderNumber: json['order_number'] as String,
        publicToken: json['public_token'] as String,
        customerName: json['customer_name'] as String,
        customerMobileE164: json['customer_mobile_e164'] as String?,
        collectionDate: json['collection_date'] as String?,
        slotLabel: json['slot_label'] as String?,
        status: json['status'] as String,
        note: json['note'] as String?,
        assignedUserName: json['assigned_user_name'] as String?,
      );

  final int id;
  final String orderNumber;
  final String publicToken;
  final String customerName;
  final String? customerMobileE164;
  final String? collectionDate;
  final String? slotLabel;
  final String status;
  final String? note;
  final String? assignedUserName;
}

class InboxData {
  const InboxData({
    required this.cashRequests,
    required this.holdLapsed,
    required this.ordersWithNotes,
    required this.recentAssisted,
    required this.recentlyExpired,
    required this.isEmpty,
  });

  factory InboxData.fromJson(Map<String, dynamic> json) {
    List<InboxRow> rows(String key) => (json[key] as List<dynamic>? ?? const [])
        .map((e) => InboxRow.fromJson(e as Map<String, dynamic>))
        .toList();
    return InboxData(
      cashRequests: rows('cash_requests'),
      holdLapsed: rows('hold_lapsed'),
      ordersWithNotes: rows('orders_with_notes'),
      recentAssisted: rows('recent_assisted'),
      recentlyExpired: rows('recently_expired'),
      isEmpty: json['is_empty'] as bool? ?? false,
    );
  }

  final List<InboxRow> cashRequests;
  final List<InboxRow> holdLapsed;
  final List<InboxRow> ordersWithNotes;
  final List<InboxRow> recentAssisted;
  final List<InboxRow> recentlyExpired;
  final bool isEmpty;
}

// ---------------------------------------------------------------- action endpoints
//
// `POST /manage/api/orders/:id/transition` and `.../assign` live outside
// `/api/v1/` (see `staff/urls_api_mobile.py`'s own docstring) — resolve
// them against the API origin manually rather than relying on dio's
// leading-slash path handling, per this screen's own build brief.

Uri _manageUrl(Dio dio, String path) => Uri.parse(dio.options.baseUrl).replace(path: path);

Future<void> _staffAssign(Dio dio, {required int orderId}) async {
  final resp = await dio.post<dynamic>(_manageUrl(dio, '/manage/api/orders/$orderId/assign').toString());
  parseStaffJson(resp, (_) => null);
}

Future<void> _staffTransition(
  Dio dio, {
  required int orderId,
  required String action,
  required String expectedStatus,
  String? reason,
  Map<String, dynamic>? payload,
}) async {
  final resp = await dio.post<dynamic>(
    _manageUrl(dio, '/manage/api/orders/$orderId/transition').toString(),
    data: {
      'action': action,
      'expected_status': expectedStatus,
      'reason': ?reason,
      'payload': ?payload,
    },
  );
  parseStaffJson(resp, (_) => null);
}
