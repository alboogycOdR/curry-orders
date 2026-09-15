import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../data/api_exception.dart';
import '../../../data/staff/staff_api.dart';
import '../../../state/api_providers.dart';
import '../../../theme/poster_tokens.dart';
import '../staff_scaffold.dart';

/// Calendar — the 8-day (today + 7) preorder grid
/// (`GET /api/v1/staff/calendar/`, `staff/api_mobile_payments.py::calendar_json`).
/// Web reference: `staff/views.py::calendar` / `templates/staff/calendar.html`.
/// Read-only, glance-only display — rendered here as a vertical stack of
/// day cards (native mobile) rather than a literal desktop grid.

class DayMeter {
  const DayMeter({required this.value, required this.of});

  factory DayMeter.fromJson(Map<String, dynamic> json) =>
      DayMeter(value: json['value'] as int, of: json['of'] as int);

  final int value;
  final int of;
}

class DaySlotHeat {
  const DaySlotHeat({
    required this.label,
    required this.occupying,
    required this.capacity,
    required this.heat,
  });

  factory DaySlotHeat.fromJson(Map<String, dynamic> json) => DaySlotHeat(
        label: json['label'] as String,
        occupying: json['occupying'] as int,
        capacity: json['capacity'] as int,
        heat: json['heat'] as String,
      );

  final String label;
  final int occupying;
  final int capacity;
  final String heat; // "low" | "mid" | "high"
}

class DishWarning {
  const DishWarning({required this.dishName, required this.usedUnits, required this.maxUnits});

  factory DishWarning.fromJson(Map<String, dynamic> json) => DishWarning(
        dishName: json['dish_name'] as String,
        usedUnits: json['used_units'] as int,
        maxUnits: json['max_units'] as int,
      );

  final String dishName;
  final int usedUnits;
  final int maxUnits;
}

class CalendarDay {
  const CalendarDay({
    required this.date,
    required this.dowLabel,
    required this.isOpen,
    required this.orders,
    required this.cash,
    required this.slots,
    required this.dishWarnings,
  });

  factory CalendarDay.fromJson(Map<String, dynamic> json) => CalendarDay(
        date: json['date'] as String,
        dowLabel: json['dow_label'] as String,
        isOpen: json['is_open'] as bool,
        orders: DayMeter.fromJson(json['orders'] as Map<String, dynamic>),
        cash: DayMeter.fromJson(json['cash'] as Map<String, dynamic>),
        slots: (json['slots'] as List<dynamic>)
            .map((e) => DaySlotHeat.fromJson(e as Map<String, dynamic>))
            .toList(),
        dishWarnings: (json['dish_warnings'] as List<dynamic>)
            .map((e) => DishWarning.fromJson(e as Map<String, dynamic>))
            .toList(),
      );

  final String date; // ISO date
  final String dowLabel;
  final bool isOpen;
  final DayMeter orders;
  final DayMeter cash;
  final List<DaySlotHeat> slots;
  final List<DishWarning> dishWarnings;
}

final calendarDaysProvider = FutureProvider.autoDispose<List<CalendarDay>>((ref) async {
  final resp = await ref.watch(apiClientProvider).dio.get<dynamic>('staff/calendar/');
  return parseStaffJson(resp, (d) {
    final days = (d as Map<String, dynamic>)['days'] as List<dynamic>;
    return days.map((e) => CalendarDay.fromJson(e as Map<String, dynamic>)).toList();
  });
});

class StaffCalendarScreen extends ConsumerWidget {
  const StaffCalendarScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final daysAsync = ref.watch(calendarDaysProvider);

    return StaffScaffold(
      title: 'Calendar',
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(calendarDaysProvider.future),
        child: daysAsync.when(
          data: (days) => ListView.separated(
            padding: const EdgeInsets.fromLTRB(
              PosterSpace.pageSidePadding, 12, PosterSpace.pageSidePadding, PosterSpace.bottomPagePadding,
            ),
            itemCount: days.length,
            separatorBuilder: (context, i) => const SizedBox(height: 12),
            itemBuilder: (context, i) => _DayCard(day: days[i]),
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

class _DayCard extends StatelessWidget {
  const _DayCard({required this.day});

  final CalendarDay day;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      // The Daily Controls screen has no date param wired into its route
      // yet (its own date-selection UI is being built in parallel and
      // may already default to today) — a plain navigation is an
      // acceptable v1; passing this specific date through is future work.
      onTap: () => context.push('/staff/daily-controls'),
      borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      child: Container(
        decoration: BoxDecoration(
          color: PosterColors.white,
          border: Border.all(color: PosterColors.border, width: 2),
          borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
        ),
        padding: const EdgeInsets.all(14),
        child: Opacity(
          opacity: day.isOpen ? 1 : 0.6,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '${day.dowLabel} ${day.date}',
                    style: PosterText.cardTitle.copyWith(fontSize: 16, color: PosterColors.navy),
                  ),
                  _StatusBadge(isOpen: day.isOpen),
                ],
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 16,
                runSpacing: 4,
                children: [
                  _MeterChip(label: 'Orders', meter: day.orders),
                  _MeterChip(label: 'Cash', meter: day.cash),
                ],
              ),
              if (day.slots.isNotEmpty) ...[
                const SizedBox(height: 10),
                Row(
                  children: [
                    for (final slot in day.slots)
                      Padding(
                        padding: const EdgeInsets.only(right: 3),
                        child: Tooltip(
                          message: '${slot.label} — ${slot.occupying}/${slot.capacity}',
                          child: Container(
                            width: 8,
                            height: 18,
                            color: _heatColor(slot.heat),
                          ),
                        ),
                      ),
                  ],
                ),
              ],
              if (day.dishWarnings.isNotEmpty) ...[
                const SizedBox(height: 10),
                for (final w in day.dishWarnings)
                  Text(
                    '⚠ ${w.dishName}: ${w.usedUnits}/${w.maxUnits} — cap or mark unavailable',
                    style: PosterText.bodyDefault.copyWith(color: PosterColors.error, fontSize: 11.5),
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.isOpen});

  final bool isOpen;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: isOpen ? PosterColors.success.withValues(alpha: 0.15) : PosterColors.muted.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(PosterSpace.radiusButton),
      ),
      child: Text(
        isOpen ? 'Open' : 'Closed',
        style: PosterText.eyebrow.copyWith(
          fontSize: 10,
          color: isOpen ? PosterColors.success : PosterColors.muted,
        ),
      ),
    );
  }
}

class _MeterChip extends StatelessWidget {
  const _MeterChip({required this.label, required this.meter});

  final String label;
  final DayMeter meter;

  @override
  Widget build(BuildContext context) {
    return Text(
      '$label: ${meter.value}/${meter.of}',
      style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
    );
  }
}

Color _heatColor(String heat) {
  switch (heat) {
    case 'high':
      return const Color(0xFFE07A5F);
    case 'mid':
      return const Color(0xFFF4D35E);
    default:
      return PosterColors.border;
  }
}
