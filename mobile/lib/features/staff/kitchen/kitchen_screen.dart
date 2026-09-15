import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api_exception.dart';
import '../../../data/staff/staff_api.dart';
import '../../../state/api_providers.dart';
import '../../../theme/poster_tokens.dart';
import '../staff_scaffold.dart';

const _weekdayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const _monthNames = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

String _isoDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

String _dateLabel(DateTime d) => '${_weekdayNames[d.weekday - 1]} ${d.day} ${_monthNames[d.month - 1]}';

/// Kitchen desk (§12.4). Backend: `GET /api/v1/staff/kitchen/?date=`
/// (`staff/api_mobile_boards.py::kitchen_json`). Date header with
/// prev/next (no route change, just a new fetch), meter chips, "Lock
/// prep list", the summary/exceptions/added-after-lock bands, then the
/// ticket run list with per-ticket and bulk start/ready actions. Every
/// action refetches rather than mutating local state, same reasoning
/// as the Inbox screen.
class KitchenScreen extends ConsumerStatefulWidget {
  const KitchenScreen({super.key});

  @override
  ConsumerState<KitchenScreen> createState() => _KitchenScreenState();
}

class _KitchenScreenState extends ConsumerState<KitchenScreen> {
  DateTime _date = DateTime.now();
  late Future<KitchenData> _future;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<KitchenData> _load() async {
    final dio = ref.read(apiClientProvider).dio;
    final resp = await dio.get<dynamic>('staff/kitchen/', queryParameters: {'date': _isoDate(_date)});
    return parseStaffJson(resp, (d) => KitchenData.fromJson(d as Map<String, dynamic>));
  }

  Future<void> _refresh() async {
    final next = _load();
    setState(() => _future = next);
    await next;
  }

  void _changeDay(int deltaDays) {
    setState(() => _date = _date.add(Duration(days: deltaDays)));
    _refresh();
  }

  Future<void> _lockPrepList() async {
    final confirmed = await _confirm(
      context,
      title: 'Lock prep list?',
      message: 'This freezes today\'s run — anything confirmed afterwards shows separately. This cannot be undone.',
    );
    if (confirmed != true) return;
    await _guarded(() async {
      final dio = ref.read(apiClientProvider).dio;
      final resp = await dio.post<dynamic>(
        _manageUrl(dio, '/manage/api/days/${_isoDate(_date)}/lock-kitchen').toString(),
      );
      parseStaffJson(resp, (_) => null);
    });
  }

  Future<void> _startKitchen(Ticket t) => _guarded(() => _transitionTicket(t, 'start_kitchen'));

  Future<void> _markReady(Ticket t) => _guarded(() => _transitionTicket(t, 'mark_ready'));

  Future<void> _transitionTicket(Ticket t, String action) async {
    final dio = ref.read(apiClientProvider).dio;
    final resp = await dio.post<dynamic>(
      _manageUrl(dio, '/manage/api/orders/${t.id}/transition').toString(),
      data: {'action': action, 'expected_status': t.status},
    );
    parseStaffJson(resp, (_) => null);
  }

  Future<void> _bulkStartAll(List<Ticket> tickets) async {
    final targets = tickets.where((t) => t.status == 'confirmed_prep' || t.status == 'cash_due').toList();
    if (targets.isEmpty) return;
    final confirmed = await _confirm(
      context,
      title: 'Start all confirmed?',
      message: 'Sends ${targets.length} order(s) to "In kitchen".',
    );
    if (confirmed != true) return;
    await _guarded(() async {
      for (final t in targets) {
        await _transitionTicket(t, 'start_kitchen');
      }
    });
  }

  Future<void> _bulkMarkReady(List<Ticket> tickets) async {
    final targets = tickets.where((t) => t.status == 'in_kitchen').toList();
    if (targets.isEmpty) return;
    final confirmed = await _confirm(
      context,
      title: 'Mark all ready?',
      message: 'Marks ${targets.length} order(s) as "Ready".',
    );
    if (confirmed != true) return;
    await _guarded(() async {
      for (final t in targets) {
        await _transitionTicket(t, 'mark_ready');
      }
    });
  }

  Future<void> _guarded(Future<void> Function() action) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await action();
      await _refresh();
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

  @override
  Widget build(BuildContext context) {
    return StaffScaffold(
      title: 'Kitchen desk',
      body: Column(
        children: [
          _DateHeader(date: _date, onPrev: () => _changeDay(-1), onNext: () => _changeDay(1)),
          Expanded(
            child: FutureBuilder<KitchenData>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return RefreshIndicator(
                    onRefresh: _refresh,
                    child: ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: const EdgeInsets.all(32),
                      children: [
                        Text(
                          snapshot.error is ApiException
                              ? (snapshot.error! as ApiException).message
                              : 'Could not load the kitchen desk.',
                          textAlign: TextAlign.center,
                          style: PosterText.bodyLarge.copyWith(color: PosterColors.error),
                        ),
                      ],
                    ),
                  );
                }
                final data = snapshot.data!;
                return RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(
                      PosterSpace.pageSidePadding, 12, PosterSpace.pageSidePadding, PosterSpace.bottomPagePadding,
                    ),
                    children: [
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          _MeterChip(label: 'Orders', meter: data.ordersMeter),
                          _MeterChip(label: 'Cash', meter: data.cashMeter),
                        ],
                      ),
                      const SizedBox(height: 12),
                      if (data.kitchenLockedAt == null)
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton.icon(
                            style: FilledButton.styleFrom(backgroundColor: PosterColors.navy),
                            onPressed: _busy ? null : _lockPrepList,
                            icon: const Icon(Icons.lock_outline_rounded),
                            label: const Text('Lock prep list'),
                          ),
                        )
                      else
                        Text('Prep list locked', style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
                      const SizedBox(height: 16),
                      _SectionHeader('Summary'),
                      if (data.summary.isEmpty)
                        Text('Nothing on the board yet.', style: PosterText.bodyDefault.copyWith(color: PosterColors.muted))
                      else
                        for (final entry in data.summary) _SummaryRow(entry: entry),
                      if (data.exceptions.isNotEmpty) ...[
                        const SizedBox(height: 16),
                        _SectionHeader('Exceptions', color: PosterColors.error),
                        for (final ex in data.exceptions) _ExceptionRow(entry: ex),
                      ],
                      if (data.kitchenLockedAt != null && data.addedAfterLock.isNotEmpty) ...[
                        const SizedBox(height: 16),
                        _SectionHeader('Added after lock', color: PosterColors.gold),
                        for (final t in data.addedAfterLock)
                          Text('${t.orderNumber} — ${t.customerName}', style: PosterText.bodyDefault.copyWith(color: PosterColors.navy)),
                      ],
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(child: _SectionHeader('Tickets')),
                          if (_busy) const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2)),
                        ],
                      ),
                      if (data.tickets.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 8, bottom: 4),
                          child: Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              OutlinedButton(
                                onPressed: _busy ? null : () => _bulkStartAll(data.tickets),
                                child: const Text('Start all confirmed'),
                              ),
                              OutlinedButton(
                                onPressed: _busy ? null : () => _bulkMarkReady(data.tickets),
                                child: const Text('Mark all ready'),
                              ),
                            ],
                          ),
                        ),
                      if (data.tickets.isEmpty)
                        Text('No tickets for this day.', style: PosterText.bodyDefault.copyWith(color: PosterColors.muted))
                      else
                        for (final t in data.tickets)
                          _TicketCard(
                            ticket: t,
                            busy: _busy,
                            onStart: () => _startKitchen(t),
                            onReady: () => _markReady(t),
                          ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

Future<bool?> _confirm(BuildContext context, {required String title, required String message}) {
  return showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.of(ctx).pop(true), child: const Text('Confirm')),
      ],
    ),
  );
}

class _DateHeader extends StatelessWidget {
  const _DateHeader({required this.date, required this.onPrev, required this.onNext});

  final DateTime date;
  final VoidCallback onPrev;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: PosterColors.bluePanel,
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          IconButton(onPressed: onPrev, icon: const Icon(Icons.chevron_left_rounded, color: PosterColors.white)),
          Text(_dateLabel(date), style: PosterText.bodyLarge.copyWith(color: PosterColors.white, fontWeight: FontWeight.w800)),
          IconButton(onPressed: onNext, icon: const Icon(Icons.chevron_right_rounded, color: PosterColors.white)),
        ],
      ),
    );
  }
}

class _MeterChip extends StatelessWidget {
  const _MeterChip({required this.label, required this.meter});

  final String label;
  final Meter meter;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: PosterColors.paper,
        border: Border.all(color: PosterColors.border, width: 1.5),
        borderRadius: BorderRadius.circular(PosterSpace.radiusButton),
      ),
      child: Text(
        '$label ${meter.value}/${meter.of}',
        style: PosterText.bodyDefault.copyWith(color: PosterColors.navy, fontWeight: FontWeight.w800),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader(this.title, {this.color});

  final String title;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Text(title.toUpperCase(), style: PosterText.eyebrow.copyWith(color: color ?? PosterColors.navy)),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  const _SummaryRow({required this.entry});

  final SummaryEntry entry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 32,
            child: Text('${entry.quantity}×', style: PosterText.bodyLarge.copyWith(color: PosterColors.navy, fontWeight: FontWeight.w800)),
          ),
          Expanded(
            child: Text(
              entry.optionSummary.isNotEmpty ? '${entry.dishName} (${entry.optionSummary})' : entry.dishName,
              style: PosterText.bodyLarge.copyWith(color: PosterColors.navy),
            ),
          ),
        ],
      ),
    );
  }
}

class _ExceptionRow extends StatelessWidget {
  const _ExceptionRow({required this.entry});

  final ExceptionEntry entry;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        border: Border.all(color: PosterColors.error, width: 1.5),
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(entry.orderNumber, style: PosterText.bodyLarge.copyWith(color: PosterColors.error, fontWeight: FontWeight.w800)),
          Text(entry.reasonText, style: PosterText.bodyDefault.copyWith(color: PosterColors.navy)),
        ],
      ),
    );
  }
}

class _TicketCard extends StatelessWidget {
  const _TicketCard({required this.ticket, required this.busy, required this.onStart, required this.onReady});

  final Ticket ticket;
  final bool busy;
  final VoidCallback onStart;
  final VoidCallback onReady;

  @override
  Widget build(BuildContext context) {
    final canStart = ticket.status == 'confirmed_prep' || ticket.status == 'cash_due';
    final canReady = ticket.status == 'in_kitchen';
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
                child: Text(ticket.orderNumber, style: PosterText.cardTitle.copyWith(fontSize: 16, color: PosterColors.navy)),
              ),
              if (ticket.slotLabel != null)
                Text(ticket.slotLabel!, style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
            ],
          ),
          Text(ticket.customerName, style: PosterText.bodyLarge.copyWith(color: PosterColors.navy)),
          Text(ticket.itemsSummary, style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
          const SizedBox(height: 6),
          Row(
            children: [
              Text(
                ticket.paymentMethod.toUpperCase(),
                style: PosterText.bodyDefault.copyWith(color: PosterColors.blue, fontWeight: FontWeight.w800),
              ),
              const Spacer(),
              if (canStart)
                FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: PosterColors.navy),
                  onPressed: busy ? null : onStart,
                  child: const Text('Start kitchen'),
                )
              else if (canReady)
                FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: PosterColors.success),
                  onPressed: busy ? null : onReady,
                  child: const Text('Mark ready'),
                )
              else
                Text(ticket.status.replaceAll('_', ' ').toUpperCase(), style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
            ],
          ),
        ],
      ),
    );
  }
}

Uri _manageUrl(Dio dio, String path) => Uri.parse(dio.options.baseUrl).replace(path: path);

// ---------------------------------------------------------------- models

class Meter {
  const Meter({required this.value, required this.of});

  factory Meter.fromJson(Map<String, dynamic> json) =>
      Meter(value: json['value'] as int, of: json['of'] as int);

  final int value;
  final int of;
}

class SummaryEntry {
  const SummaryEntry({
    required this.dishName,
    required this.optionSummary,
    required this.quantity,
    required this.orderNumbers,
  });

  factory SummaryEntry.fromJson(Map<String, dynamic> json) => SummaryEntry(
        dishName: json['dish_name'] as String,
        optionSummary: json['option_summary'] as String? ?? '',
        quantity: json['quantity'] as int,
        orderNumbers: (json['order_numbers'] as List<dynamic>? ?? const []).cast<String>(),
      );

  final String dishName;
  final String optionSummary;
  final int quantity;
  final List<String> orderNumbers;
}

class ExceptionEntry {
  const ExceptionEntry({required this.orderNumber, required this.reasonText});

  factory ExceptionEntry.fromJson(Map<String, dynamic> json) => ExceptionEntry(
        orderNumber: json['order_number'] as String,
        reasonText: json['reason_text'] as String,
      );

  final String orderNumber;
  final String reasonText;
}

class Ticket {
  const Ticket({
    required this.id,
    required this.orderNumber,
    required this.slotLabel,
    required this.customerName,
    required this.itemsSummary,
    required this.paymentMethod,
    required this.status,
  });

  factory Ticket.fromJson(Map<String, dynamic> json) => Ticket(
        id: json['id'] as int,
        orderNumber: json['order_number'] as String,
        slotLabel: json['slot_label'] as String?,
        customerName: json['customer_name'] as String,
        itemsSummary: json['items_summary'] as String,
        paymentMethod: json['payment_method'] as String,
        status: json['status'] as String,
      );

  final int id;
  final String orderNumber;
  final String? slotLabel;
  final String customerName;
  final String itemsSummary;
  final String paymentMethod;
  final String status;
}

class KitchenData {
  const KitchenData({
    required this.date,
    required this.kitchenLockedAt,
    required this.ordersMeter,
    required this.cashMeter,
    required this.summary,
    required this.exceptions,
    required this.addedAfterLock,
    required this.tickets,
  });

  factory KitchenData.fromJson(Map<String, dynamic> json) {
    final meters = json['meters'] as Map<String, dynamic>;
    return KitchenData(
      date: json['date'] as String,
      kitchenLockedAt: json['kitchen_locked_at'] as String?,
      ordersMeter: Meter.fromJson(meters['orders'] as Map<String, dynamic>),
      cashMeter: Meter.fromJson(meters['cash'] as Map<String, dynamic>),
      summary: (json['summary'] as List<dynamic>? ?? const [])
          .map((e) => SummaryEntry.fromJson(e as Map<String, dynamic>))
          .toList(),
      exceptions: (json['exceptions'] as List<dynamic>? ?? const [])
          .map((e) => ExceptionEntry.fromJson(e as Map<String, dynamic>))
          .toList(),
      addedAfterLock: (json['added_after_lock'] as List<dynamic>? ?? const [])
          .map((e) => Ticket.fromJson(e as Map<String, dynamic>))
          .toList(),
      tickets: (json['tickets'] as List<dynamic>? ?? const [])
          .map((e) => Ticket.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  final String date;
  final String? kitchenLockedAt;
  final Meter ordersMeter;
  final Meter cashMeter;
  final List<SummaryEntry> summary;
  final List<ExceptionEntry> exceptions;
  final List<Ticket> addedAfterLock;
  final List<Ticket> tickets;
}
