import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../data/staff/staff_api.dart';
import '../../../state/api_providers.dart';
import '../../../theme/poster_tokens.dart';
import '../../../util/money.dart';
import '../staff_scaffold.dart';

/// One row of `GET /api/v1/staff/menu/` (`staff/api_mobile_menu.py::menu_list_json`).
/// Kept private/co-located with this screen — [DishFormScreen] fetches
/// its own full detail shape independently via [DishDetail] in
/// `dish_form_screen.dart` rather than sharing this row model.
class _DishRow {
  const _DishRow({
    required this.id,
    required this.category,
    required this.sortOrder,
    required this.name,
    required this.isFeatured,
    required this.priceCents,
    required this.isActiveOnMenu,
    required this.isArchived,
    required this.occupyingOrderCount,
  });

  factory _DishRow.fromJson(Map<String, dynamic> json) => _DishRow(
        id: json['id'] as int,
        category: json['category'] as String?,
        sortOrder: json['sort_order'] as int,
        name: json['name'] as String,
        isFeatured: json['is_featured'] as bool,
        priceCents: json['price_cents'] as int,
        isActiveOnMenu: json['is_active_on_menu'] as bool,
        isArchived: json['is_archived'] as bool,
        occupyingOrderCount: json['occupying_order_count'] as int,
      );

  final int id;
  final String? category;
  final int sortOrder;
  final String name;
  final bool isFeatured;
  final int priceCents;
  final bool isActiveOnMenu;
  final bool isArchived;
  final int occupyingOrderCount;
}

/// Not `autoDispose` — [DishFormScreen] (a different, independently
/// pushed route) invalidates this provider after any create/save/
/// archive/unarchive so the list is fresh the moment the user navigates
/// back to it (a plain `context.push`/pop pair, so this screen's widget
/// — and its watch of this provider — stays alive underneath the whole
/// time; no result-passing plumbing needed).
final staffMenuListProvider = FutureProvider<List<_DishRow>>((ref) async {
  final resp = await ref.watch(apiClientProvider).dio.get<dynamic>('staff/menu/');
  return parseStaffJson(resp, (d) {
    final rows = (d as Map<String, dynamic>)['dishes'] as List<dynamic>;
    return rows.map((r) => _DishRow.fromJson(r as Map<String, dynamic>)).toList();
  });
});

const _allCategoriesLabel = 'All categories';

class StaffMenuListScreen extends ConsumerStatefulWidget {
  const StaffMenuListScreen({super.key});

  @override
  ConsumerState<StaffMenuListScreen> createState() => _StaffMenuListScreenState();
}

class _StaffMenuListScreenState extends ConsumerState<StaffMenuListScreen> {
  final _searchController = TextEditingController();
  String _search = '';
  String _category = _allCategoriesLabel;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final menuAsync = ref.watch(staffMenuListProvider);

    return StaffScaffold(
      title: 'Menu editor',
      floatingActionButton: FloatingActionButton(
        backgroundColor: PosterColors.gold,
        foregroundColor: PosterColors.navy,
        onPressed: () async {
          await context.push<void>('/staff/menu/new');
          ref.invalidate(staffMenuListProvider);
        },
        child: const Icon(Icons.add),
      ),
      body: menuAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
            child: Text('Could not load the menu: $err', style: PosterText.bodyDefault),
          ),
        ),
        data: (dishes) {
          final categories = [
            _allCategoriesLabel,
            ...{for (final d in dishes) if ((d.category ?? '').isNotEmpty) d.category!},
          ];
          final filtered = dishes.where((d) {
            final matchesCategory = _category == _allCategoriesLabel || d.category == _category;
            final matchesSearch =
                _search.isEmpty || d.name.toLowerCase().contains(_search.toLowerCase());
            return matchesCategory && matchesSearch;
          }).toList();

          return Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  PosterSpace.pageSidePadding, 12, PosterSpace.pageSidePadding, 4,
                ),
                child: TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: 'Search dishes…',
                    prefixIcon: const Icon(Icons.search),
                    filled: true,
                    fillColor: PosterColors.white,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
                      borderSide: const BorderSide(color: PosterColors.border),
                    ),
                  ),
                  onChanged: (v) => setState(() => _search = v),
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: PosterSpace.pageSidePadding, vertical: 4,
                ),
                child: SizedBox(
                  height: 36,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: categories.length,
                    separatorBuilder: (context, index) => const SizedBox(width: 8),
                    itemBuilder: (context, i) {
                      final c = categories[i];
                      final selected = c == _category;
                      return ChoiceChip(
                        label: Text(c),
                        selected: selected,
                        selectedColor: PosterColors.navy,
                        labelStyle: PosterText.bodyDefault.copyWith(
                          color: selected ? PosterColors.white : PosterColors.navy,
                        ),
                        backgroundColor: PosterColors.white,
                        side: const BorderSide(color: PosterColors.border),
                        onSelected: (_) => setState(() => _category = c),
                      );
                    },
                  ),
                ),
              ),
              Expanded(
                child: filtered.isEmpty
                    ? Center(
                        child: Text('No dishes match.', style: PosterText.bodyDefault),
                      )
                    : RefreshIndicator(
                        onRefresh: () async => ref.invalidate(staffMenuListProvider),
                        child: ListView.separated(
                          padding: const EdgeInsets.fromLTRB(
                            PosterSpace.pageSidePadding, 8, PosterSpace.pageSidePadding,
                            PosterSpace.bottomPagePadding,
                          ),
                          itemCount: filtered.length,
                          separatorBuilder: (context, index) => const SizedBox(height: 8),
                          itemBuilder: (context, i) => _DishListTile(
                            dish: filtered[i],
                            onTap: () async {
                              await context.push<void>('/staff/menu/${filtered[i].id}');
                              ref.invalidate(staffMenuListProvider);
                            },
                          ),
                        ),
                      ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _DishListTile extends StatelessWidget {
  const _DishListTile({required this.dish, required this.onTap});

  final _DishRow dish;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: PosterColors.white,
      borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      child: InkWell(
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
        onTap: onTap,
        child: Container(
          decoration: BoxDecoration(
            border: Border.all(color: PosterColors.border),
            borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
          ),
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        if (dish.isFeatured)
                          const Padding(
                            padding: EdgeInsets.only(right: 4),
                            child: Icon(Icons.star_rounded, color: PosterColors.gold, size: 18),
                          ),
                        Expanded(
                          child: Text(
                            dish.name,
                            style: PosterText.cardTitle.copyWith(fontSize: 17, color: PosterColors.navy),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      dish.category?.isNotEmpty == true ? dish.category! : 'Uncategorised',
                      style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
                    ),
                    if (dish.occupyingOrderCount > 0)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Row(
                          children: [
                            const Icon(Icons.info_outline, size: 14, color: PosterColors.error),
                            const SizedBox(width: 4),
                            Text(
                              '${dish.occupyingOrderCount} occupying order'
                              '${dish.occupyingOrderCount == 1 ? '' : 's'}',
                              style: PosterText.bodyDefault.copyWith(
                                color: PosterColors.error, fontSize: 11,
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    formatCents(dish.priceCents),
                    style: PosterText.bodyLarge.copyWith(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 4),
                  _StatusBadge(isArchived: dish.isArchived, isActive: dish.isActiveOnMenu),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.isArchived, required this.isActive});

  final bool isArchived;
  final bool isActive;

  @override
  Widget build(BuildContext context) {
    final String label;
    final Color color;
    if (isArchived) {
      label = 'ARCHIVED';
      color = PosterColors.muted;
    } else if (isActive) {
      label = 'ACTIVE';
      color = PosterColors.success;
    } else {
      label = 'HIDDEN';
      color = PosterColors.error;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: PosterText.metadata.copyWith(color: color, fontSize: 10),
      ),
    );
  }
}
