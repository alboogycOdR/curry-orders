import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api_exception.dart';
import '../../../data/staff/staff_api.dart';
import '../../../state/api_providers.dart';
import '../../../theme/poster_tokens.dart';
import '../staff_scaffold.dart';

/// Daily controls (docs/mobile/FLUTTER_APP_PLAN.md Phase 6). Backend:
/// `GET/POST /api/v1/staff/days/<date>/`
/// (`staff/api_mobile_daily_controls.py::daily_controls_json`) — GET
/// returns the current state, POST validates+saves and returns the new
/// state in the same shape. "Move all to…" reuses the existing action
/// endpoint (`POST /manage/api/days/<date>/slots/<slot_id>/move-all`,
/// `staff.api.move_all_orders`) directly, same URL the web boards' own
/// JS calls.
///
/// Any staff role — this is not owner-gated (matches the web view).
class DailyControlsScreen extends ConsumerStatefulWidget {
  const DailyControlsScreen({super.key});

  @override
  ConsumerState<DailyControlsScreen> createState() => _DailyControlsScreenState();
}

class _DailyControlsScreenState extends ConsumerState<DailyControlsScreen> {
  DateTime _date = DateTime.now();
  bool _loading = true;
  bool _saving = false;
  String? _loadError;

  bool _isOpen = true;
  final _capController = TextEditingController();
  TimeOfDay? _cutoff;
  TimeOfDay? _windowStart;
  TimeOfDay? _windowEnd;
  final _notesController = TextEditingController();

  List<_SlotControl> _slots = [];
  List<_DishControl> _dishes = [];

  String get _dateStr => _isoDate(_date);

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _capController.dispose();
    _notesController.dispose();
    _disposeRowControllers();
    super.dispose();
  }

  void _disposeRowControllers() {
    for (final s in _slots) {
      s.capacityController.dispose();
    }
    for (final d in _dishes) {
      d.maxUnitsController.dispose();
    }
  }

  // -------------------------------------------------------------- data

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    try {
      final dio = ref.read(apiClientProvider).dio;
      final resp = await dio.get<dynamic>('staff/days/$_dateStr/');
      final json = parseStaffJson(resp, (d) => d as Map<String, dynamic>);
      _applyJson(json);
      if (mounted) setState(() => _loading = false);
    } on ApiException catch (e) {
      if (mounted) {
        setState(() {
          _loading = false;
          _loadError = e.message;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _loading = false;
          _loadError = 'Something went wrong loading this day.';
        });
      }
    }
  }

  void _applyJson(Map<String, dynamic> json) {
    final day = json['day'] as Map<String, dynamic>;
    _isOpen = day['is_open'] as bool;
    _capController.text = (day['daily_order_cap'] as int).toString();
    _cutoff = _parseTimeOfDay(day['cutoff_time'] as String?);
    _windowStart = _parseTimeOfDay(day['window_start'] as String?);
    _windowEnd = _parseTimeOfDay(day['window_end'] as String?);
    _notesController.text = (day['notes_internal'] as String?) ?? '';

    _disposeRowControllers();
    _slots = (json['slots'] as List<dynamic>? ?? [])
        .map((e) => _SlotControl.fromJson(e as Map<String, dynamic>))
        .toList();
    _dishes = (json['dishes'] as List<dynamic>? ?? [])
        .map((e) => _DishControl.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Map<String, dynamic> _buildPayload({required bool confirmAffectingOrders}) {
    return {
      'day': {
        'is_open': _isOpen,
        'daily_order_cap': int.tryParse(_capController.text.trim()) ?? 0,
        'cutoff_time': _cutoff != null ? _formatTimeOfDay(_cutoff!) : null,
        'window_start': _windowStart != null ? _formatTimeOfDay(_windowStart!) : null,
        'window_end': _windowEnd != null ? _formatTimeOfDay(_windowEnd!) : null,
        'notes_internal': _notesController.text.trim(),
      },
      'slots': [
        for (final s in _slots)
          {
            'id': s.id,
            'capacity': int.tryParse(s.capacityController.text.trim()) ?? s.minCapacity,
            'closed': s.closed,
          },
      ],
      'dishes': [
        for (final d in _dishes)
          {
            'id': d.id,
            'available': d.available,
            'max_units': d.maxUnitsController.text.trim().isEmpty
                ? null
                : int.tryParse(d.maxUnitsController.text.trim()),
          },
      ],
      'confirm_affecting_orders': confirmAffectingOrders,
    };
  }

  Future<void> _save({required bool confirmAffectingOrders}) async {
    setState(() => _saving = true);
    try {
      final dio = ref.read(apiClientProvider).dio;
      final resp = await dio.post<dynamic>(
        'staff/days/$_dateStr/',
        data: _buildPayload(confirmAffectingOrders: confirmAffectingOrders),
      );
      final status = resp.statusCode ?? 0;
      final data = resp.data;
      if (status >= 200 && status < 300 && data is Map<String, dynamic>) {
        _applyJson(data);
        if (mounted) {
          ScaffoldMessenger.of(context)
              .showSnackBar(const SnackBar(content: Text('Daily controls saved.')));
        }
        return;
      }
      if (data is Map<String, dynamic> && data['error'] == 'confirmation_required') {
        final affected = (data['affected_orders'] as List<dynamic>? ?? [])
            .map((e) => _AffectedOrder.fromJson(e as Map<String, dynamic>))
            .toList();
        await _showConfirmDialog(affected);
        return;
      }
      // Any other error shape -- let the shared parser throw the right
      // ApiException (message + field errors) for the catch block below.
      parseStaffJson(resp, (_) => null);
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _moveAllOrders(int fromSlotId, int toSlotId) async {
    try {
      final dio = ref.read(apiClientProvider).dio;
      final origin = Uri.parse(dio.options.baseUrl);
      final uri = origin.replace(path: '/manage/api/days/$_dateStr/slots/$fromSlotId/move-all');
      final resp = await dio.postUri<dynamic>(uri, data: {'to_slot_id': toSlotId});
      final data = resp.data;
      final status = resp.statusCode ?? 0;
      if (status >= 200 && status < 300 && data is Map<String, dynamic>) {
        final moved = data['moved'] as int? ?? 0;
        final failures = data['failures'] as List<dynamic>? ?? [];
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                'Moved $moved order(s).${failures.isNotEmpty ? ' ${failures.length} could not be moved.' : ''}',
              ),
            ),
          );
        }
      } else if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text("Couldn't move those orders.")));
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text("Couldn't move those orders.")));
      }
    }
  }

  void _changeDate(int deltaDays) {
    setState(() => _date = _date.add(Duration(days: deltaDays)));
    _load();
  }

  // -------------------------------------------------------------- confirm dialog

  Future<void> _showConfirmDialog(List<_AffectedOrder> affected) async {
    if (!mounted) return;
    final closingSlots =
        _slots.where((s) => s.closed && !s.originallyClosed && s.occupyingCount > 0).toList();
    var understood = false;
    final moveTargets = <int, int?>{};

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: const Text('These orders will be affected'),
          content: SizedBox(
            width: double.maxFinite,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final o in affected)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Text('${o.orderNumber} — ${o.customerName} (${o.status})'),
                    ),
                  if (closingSlots.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Text(
                      'Move orders out of a closing slot first, if you prefer:',
                      style: PosterText.bodyDefault.copyWith(fontWeight: FontWeight.w700),
                    ),
                    for (final slot in closingSlots)
                      _MoveAllRow(
                        slot: slot,
                        otherOpenSlots: _slots.where((s) => s.id != slot.id && !s.closed).toList(),
                        selectedTarget: moveTargets[slot.id],
                        onTargetChanged: (v) => setDialogState(() => moveTargets[slot.id] = v),
                        onMove: (targetId) async {
                          Navigator.of(dialogContext).pop();
                          await _moveAllOrders(slot.id, targetId);
                          await _load();
                        },
                      ),
                  ],
                  const SizedBox(height: 12),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    value: understood,
                    activeColor: PosterColors.blue,
                    onChanged: (v) => setDialogState(() => understood = v ?? false),
                    title: const Text(
                      'I understand this affects the orders listed and want to save anyway.',
                    ),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: understood
                  ? () async {
                      Navigator.of(dialogContext).pop();
                      await _save(confirmAffectingOrders: true);
                    }
                  : null,
              child: const Text('Save anyway'),
            ),
          ],
        ),
      ),
    );
  }

  // -------------------------------------------------------------- build

  @override
  Widget build(BuildContext context) {
    return StaffScaffold(
      title: 'Daily controls',
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: PosterColors.blue))
          : _loadError != null
              ? _ErrorView(message: _loadError!, onRetry: _load)
              : _buildContent(context),
    );
  }

  Widget _buildContent(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.only(bottom: PosterSpace.bottomPagePadding),
      children: [
        _dateHeader(),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: PosterSpace.pageSidePadding),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 16),
              _daySection(),
              _slotsSection(),
              _dishesSection(),
              _saveButton(),
            ],
          ),
        ),
      ],
    );
  }

  Widget _dateHeader() {
    return Container(
      color: PosterColors.navy,
      padding: const EdgeInsets.symmetric(horizontal: PosterSpace.pageSidePadding, vertical: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          IconButton(
            icon: const Icon(Icons.chevron_left_rounded, color: PosterColors.white),
            onPressed: _saving ? null : () => _changeDate(-1),
          ),
          Text(_dateStr, style: PosterText.cardTitle.copyWith(color: PosterColors.white)),
          IconButton(
            icon: const Icon(Icons.chevron_right_rounded, color: PosterColors.white),
            onPressed: _saving ? null : () => _changeDate(1),
          ),
        ],
      ),
    );
  }

  Widget _daySection() {
    return _SectionCard(
      title: 'Day settings',
      children: [
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Day open', style: PosterText.bodyLarge),
          value: _isOpen,
          activeThumbColor: PosterColors.blue,
          onChanged: _saving ? null : (v) => setState(() => _isOpen = v),
        ),
        TextField(
          controller: _capController,
          keyboardType: TextInputType.number,
          enabled: !_saving,
          decoration: const InputDecoration(labelText: 'Daily order cap'),
        ),
        const SizedBox(height: 8),
        _timeRow('Cut-off time', _cutoff, (t) => setState(() => _cutoff = t)),
        _timeRow('Window start', _windowStart, (t) => setState(() => _windowStart = t)),
        _timeRow('Window end', _windowEnd, (t) => setState(() => _windowEnd = t)),
        const SizedBox(height: 8),
        TextField(
          controller: _notesController,
          maxLines: 3,
          enabled: !_saving,
          decoration: const InputDecoration(labelText: 'Internal notes'),
        ),
      ],
    );
  }

  Widget _timeRow(String label, TimeOfDay? value, ValueChanged<TimeOfDay> onChanged) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(label, style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
      trailing: Text(
        value != null ? value.format(context) : '—',
        style: PosterText.bodyLarge.copyWith(color: PosterColors.navy, fontWeight: FontWeight.w700),
      ),
      onTap: _saving
          ? null
          : () async {
              final picked = await showTimePicker(
                context: context,
                initialTime: value ?? TimeOfDay.now(),
              );
              if (picked != null) onChanged(picked);
            },
    );
  }

  Widget _slotsSection() {
    return _SectionCard(
      title: 'Slots',
      children: [for (final slot in _slots) _slotRow(slot)],
    );
  }

  Widget _slotRow(_SlotControl slot) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  slot.label,
                  style: PosterText.bodyLarge.copyWith(color: PosterColors.navy, fontWeight: FontWeight.w700),
                ),
              ),
              SizedBox(
                width: 72,
                child: TextField(
                  controller: slot.capacityController,
                  keyboardType: TextInputType.number,
                  textAlign: TextAlign.center,
                  enabled: !_saving,
                  decoration: const InputDecoration(isDense: true),
                ),
              ),
            ],
          ),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Occupied: ${slot.occupyingCount} (capacity can\'t go below this)',
                  style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
                ),
              ),
              const Text('Closed', style: PosterText.bodyDefault),
              Checkbox(
                value: slot.closed,
                activeColor: PosterColors.blue,
                onChanged: _saving ? null : (v) => setState(() => slot.closed = v ?? false),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _dishesSection() {
    return _SectionCard(
      title: 'Dishes',
      children: [for (final dish in _dishes) _dishRow(dish)],
    );
  }

  Widget _dishRow(_DishControl dish) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  dish.name,
                  style: PosterText.bodyLarge.copyWith(color: PosterColors.navy, fontWeight: FontWeight.w700),
                ),
              ),
              Switch(
                value: dish.available,
                activeThumbColor: PosterColors.blue,
                onChanged: _saving ? null : (v) => setState(() => dish.available = v),
              ),
            ],
          ),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Used today: ${dish.usedToday}',
                  style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
                ),
              ),
              SizedBox(
                width: 110,
                child: TextField(
                  controller: dish.maxUnitsController,
                  keyboardType: TextInputType.number,
                  textAlign: TextAlign.center,
                  enabled: !_saving,
                  decoration: const InputDecoration(isDense: true, hintText: 'Max units'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _saveButton() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 20),
      child: SizedBox(
        width: double.infinity,
        child: FilledButton(
          style: FilledButton.styleFrom(
            backgroundColor: PosterColors.blue,
            padding: const EdgeInsets.symmetric(vertical: 14),
          ),
          onPressed: _saving ? null : () => _save(confirmAffectingOrders: false),
          child: _saving
              ? const SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(strokeWidth: 2, color: PosterColors.white),
                )
              : Text('Save', style: PosterText.button),
        ),
      ),
    );
  }
}

// -------------------------------------------------------------- helpers

String _isoDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

TimeOfDay? _parseTimeOfDay(String? raw) {
  if (raw == null || raw.isEmpty) return null;
  final parts = raw.split(':');
  if (parts.length < 2) return null;
  final h = int.tryParse(parts[0]);
  final m = int.tryParse(parts[1]);
  if (h == null || m == null) return null;
  return TimeOfDay(hour: h, minute: m);
}

String _formatTimeOfDay(TimeOfDay t) =>
    '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

// -------------------------------------------------------------- row models

class _SlotControl {
  _SlotControl({
    required this.id,
    required this.label,
    required this.minCapacity,
    required this.occupyingCount,
    required int capacity,
    required this.closed,
  })  : capacityController = TextEditingController(text: capacity.toString()),
        originallyClosed = closed;

  factory _SlotControl.fromJson(Map<String, dynamic> json) => _SlotControl(
        id: json['id'] as int,
        label: json['label'] as String,
        minCapacity: json['min_capacity'] as int,
        occupyingCount: json['occupying_count'] as int,
        capacity: json['capacity'] as int,
        closed: json['closed'] as bool,
      );

  final int id;
  final String label;
  final int minCapacity;
  final int occupyingCount;
  final TextEditingController capacityController;
  bool closed;
  final bool originallyClosed;
}

class _DishControl {
  _DishControl({
    required this.id,
    required this.name,
    required this.usedToday,
    required this.available,
    int? maxUnits,
  }) : maxUnitsController = TextEditingController(text: maxUnits?.toString() ?? '');

  factory _DishControl.fromJson(Map<String, dynamic> json) => _DishControl(
        id: json['id'] as int,
        name: json['name'] as String,
        usedToday: json['used_today'] as int,
        available: json['available'] as bool,
        maxUnits: json['max_units'] as int?,
      );

  final int id;
  final String name;
  final int usedToday;
  bool available;
  final TextEditingController maxUnitsController;
}

class _AffectedOrder {
  _AffectedOrder({required this.orderNumber, required this.customerName, required this.status});

  factory _AffectedOrder.fromJson(Map<String, dynamic> json) => _AffectedOrder(
        orderNumber: json['order_number'] as String,
        customerName: json['customer_name'] as String,
        status: json['status'] as String,
      );

  final String orderNumber;
  final String customerName;
  final String status;
}

// -------------------------------------------------------------- small widgets

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: PosterColors.white,
        border: Border.all(color: PosterColors.border),
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: PosterText.eyebrow.copyWith(color: PosterColors.muted)),
          const SizedBox(height: 8),
          ...children,
        ],
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(message, style: PosterText.bodyLarge, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}

class _MoveAllRow extends StatelessWidget {
  const _MoveAllRow({
    required this.slot,
    required this.otherOpenSlots,
    required this.selectedTarget,
    required this.onTargetChanged,
    required this.onMove,
  });

  final _SlotControl slot;
  final List<_SlotControl> otherOpenSlots;
  final int? selectedTarget;
  final ValueChanged<int?> onTargetChanged;
  final Future<void> Function(int targetId) onMove;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Expanded(
            child: DropdownButton<int>(
              isExpanded: true,
              hint: Text('Move ${slot.label} orders to…'),
              value: selectedTarget,
              items: [
                for (final opt in otherOpenSlots)
                  DropdownMenuItem(value: opt.id, child: Text(opt.label)),
              ],
              onChanged: otherOpenSlots.isEmpty ? null : onTargetChanged,
            ),
          ),
          const SizedBox(width: 8),
          FilledButton(
            onPressed: selectedTarget == null ? null : () => onMove(selectedTarget!),
            child: const Text('Move all'),
          ),
        ],
      ),
    );
  }
}
