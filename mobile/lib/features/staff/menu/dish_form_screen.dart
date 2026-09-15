import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../data/api_exception.dart';
import '../../../data/staff/staff_api.dart';
import '../../../state/api_providers.dart';
import '../../../theme/poster_tokens.dart';
import '../../../util/money.dart';
import '../staff_scaffold.dart';
import 'menu_list_screen.dart' show staffMenuListProvider;

/// `dish_option_values` row (`staff/api_mobile_menu.py::_value_json`).
class DishOptionValue {
  const DishOptionValue({
    required this.id,
    required this.name,
    required this.priceDeltaCents,
    required this.sortOrder,
    required this.isAvailable,
  });

  factory DishOptionValue.fromJson(Map<String, dynamic> json) => DishOptionValue(
        id: json['id'] as int,
        name: json['name'] as String,
        priceDeltaCents: json['price_delta_cents'] as int,
        sortOrder: json['sort_order'] as int,
        isAvailable: json['is_available'] as bool,
      );

  final int id;
  final String name;
  final int priceDeltaCents;
  final int sortOrder;
  final bool isAvailable;
}

/// `dish_options` row (`staff/api_mobile_menu.py::_option_json`).
class DishOption {
  const DishOption({
    required this.id,
    required this.name,
    required this.required,
    required this.sortOrder,
    required this.values,
  });

  factory DishOption.fromJson(Map<String, dynamic> json) => DishOption(
        id: json['id'] as int,
        name: json['name'] as String,
        required: json['required'] as bool,
        sortOrder: json['sort_order'] as int,
        values: (json['values'] as List<dynamic>)
            .map((v) => DishOptionValue.fromJson(v as Map<String, dynamic>))
            .toList(),
      );

  final int id;
  final String name;
  final bool required;
  final int sortOrder;
  final List<DishOptionValue> values;
}

/// Full dish shape from `GET/POST /api/v1/staff/menu/<id>/` (and the
/// `POST /api/v1/staff/menu/new/` create response, which additionally
/// carries `slug` — see `_dish_payload`'s own docstring in
/// `staff/api_mobile_menu.py` for why the edit shape omits it).
class DishDetail {
  const DishDetail({
    required this.id,
    required this.name,
    required this.priceCents,
    required this.portionLabel,
    required this.shortDescription,
    required this.longDescription,
    required this.spiceDefault,
    required this.allergenText,
    required this.dietaryTags,
    required this.category,
    required this.sortOrder,
    required this.isActiveOnMenu,
    required this.allowNotes,
    required this.isFeatured,
    required this.isArchived,
    required this.occupyingOrderCount,
    required this.photoUrl,
  });

  factory DishDetail.fromJson(Map<String, dynamic> json) => DishDetail(
        id: json['id'] as int,
        name: json['name'] as String,
        priceCents: json['price_cents'] as int,
        portionLabel: (json['portion_label'] as String?) ?? '',
        shortDescription: (json['short_description'] as String?) ?? '',
        longDescription: (json['long_description'] as String?) ?? '',
        spiceDefault: (json['spice_default'] as String?) ?? '',
        allergenText: (json['allergen_text'] as String?) ?? '',
        dietaryTags: (json['dietary_tags'] as List<dynamic>).map((e) => e as String).toList(),
        category: (json['category'] as String?) ?? '',
        sortOrder: json['sort_order'] as int,
        isActiveOnMenu: json['is_active_on_menu'] as bool,
        allowNotes: json['allow_notes'] as bool,
        isFeatured: json['is_featured'] as bool,
        isArchived: json['is_archived'] as bool,
        occupyingOrderCount: json['occupying_order_count'] as int,
        photoUrl: (json['photo_url'] as String?) ?? '',
      );

  final int id;
  final String name;
  final int priceCents;
  final String portionLabel;
  final String shortDescription;
  final String longDescription;
  final String spiceDefault;
  final String allergenText;
  final List<String> dietaryTags;
  final String category;
  final int sortOrder;
  final bool isActiveOnMenu;
  final bool allowNotes;
  final bool isFeatured;
  final bool isArchived;
  final int occupyingOrderCount;
  final String photoUrl;
}

/// `options` isn't part of [DishDetail] itself (kept separate so a plain
/// field save's response — which carries the same `options` array right
/// back — doesn't force every caller to re-parse it into the object
/// graph) — parsed from the raw dish JSON alongside [DishDetail.fromJson].
List<DishOption> _optionsFromDishJson(Map<String, dynamic> json) =>
    (json['options'] as List<dynamic>)
        .map((o) => DishOption.fromJson(o as Map<String, dynamic>))
        .toList();

String _centsToRandText(int cents) => (cents / 100).toStringAsFixed(2);

int _randTextToCents(String text) {
  final value = double.tryParse(text.trim().replaceAll(',', '.')) ?? 0;
  return (value * 100).round();
}

String _signedRand(int cents) => cents >= 0 ? '+${formatCents(cents)}' : formatCents(cents);

class DishFormScreen extends ConsumerStatefulWidget {
  const DishFormScreen({super.key, this.dishId});

  final int? dishId;

  @override
  ConsumerState<DishFormScreen> createState() => _DishFormScreenState();
}

class _DishFormScreenState extends ConsumerState<DishFormScreen> {
  bool get _isEditing => widget.dishId != null;

  late Future<void> _loadFuture;
  DishDetail? _dish;
  List<DishOption> _options = [];
  List<String> _categorySuggestions = [];
  Map<String, String>? _fieldErrors;
  bool _saving = false;
  bool _uploadingImage = false;

  final _slugController = TextEditingController();
  final _nameController = TextEditingController();
  final _priceController = TextEditingController(text: '0.00');
  final _portionController = TextEditingController();
  final _shortDescController = TextEditingController();
  final _longDescController = TextEditingController();
  final _spiceController = TextEditingController();
  final _allergenController = TextEditingController();
  final _dietaryTagsController = TextEditingController();
  final _categoryController = TextEditingController();
  final _sortOrderController = TextEditingController(text: '0');
  bool _isActiveOnMenu = false;
  bool _allowNotes = true;
  bool _isFeatured = false;

  final _newOptionNameController = TextEditingController();
  final _newOptionSortController = TextEditingController(text: '0');
  bool _newOptionRequired = true;

  @override
  void initState() {
    super.initState();
    _loadFuture = _load();
  }

  @override
  void dispose() {
    _slugController.dispose();
    _nameController.dispose();
    _priceController.dispose();
    _portionController.dispose();
    _shortDescController.dispose();
    _longDescController.dispose();
    _spiceController.dispose();
    _allergenController.dispose();
    _dietaryTagsController.dispose();
    _categoryController.dispose();
    _sortOrderController.dispose();
    _newOptionNameController.dispose();
    _newOptionSortController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final dio = ref.read(apiClientProvider).dio;
    if (_isEditing) {
      final resp = await dio.get<dynamic>('staff/menu/${widget.dishId}/');
      final dish = parseStaffJson(resp, (d) {
        final body = (d as Map<String, dynamic>)['dish'] as Map<String, dynamic>;
        return (DishDetail.fromJson(body), body);
      });
      _applyDish(dish.$1, dish.$2, fillControllers: true);
    } else {
      final resp = await dio.get<dynamic>('staff/menu/new/');
      _categorySuggestions = parseStaffJson(
        resp,
        (d) => ((d as Map<String, dynamic>)['categories'] as List<dynamic>)
            .map((e) => e as String)
            .toList(),
      );
    }
  }

  void _applyDish(DishDetail dish, Map<String, dynamic> raw, {bool fillControllers = false}) {
    _dish = dish;
    _options = _optionsFromDishJson(raw);
    if (fillControllers) {
      _nameController.text = dish.name;
      _priceController.text = _centsToRandText(dish.priceCents);
      _portionController.text = dish.portionLabel;
      _shortDescController.text = dish.shortDescription;
      _longDescController.text = dish.longDescription;
      _spiceController.text = dish.spiceDefault;
      _allergenController.text = dish.allergenText;
      _dietaryTagsController.text = dish.dietaryTags.join(', ');
      _categoryController.text = dish.category;
      _sortOrderController.text = dish.sortOrder.toString();
      _isActiveOnMenu = dish.isActiveOnMenu;
      _allowNotes = dish.allowNotes;
      _isFeatured = dish.isFeatured;
    }
  }

  Map<String, dynamic> _fieldsBody() {
    final tags = _dietaryTagsController.text
        .split(',')
        .map((t) => t.trim())
        .where((t) => t.isNotEmpty)
        .toList();
    return {
      'name': _nameController.text.trim(),
      'price_cents': _randTextToCents(_priceController.text),
      'portion_label': _portionController.text.trim(),
      'short_description': _shortDescController.text.trim(),
      'long_description': _longDescController.text.trim(),
      'spice_default': _spiceController.text.trim(),
      'allergen_text': _allergenController.text.trim(),
      'dietary_tags': tags,
      'category': _categoryController.text.trim(),
      'sort_order': int.tryParse(_sortOrderController.text.trim()) ?? 0,
      'is_active_on_menu': _isActiveOnMenu,
      'allow_notes': _allowNotes,
      'is_featured': _isFeatured,
    };
  }

  void _showError(Object err) {
    if (!mounted) return;
    final message = err is ApiException ? err.message : 'Something went wrong.';
    final fields = err is ApiException ? err.fields : null;
    setState(() => _fieldErrors = fields);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _fieldErrors = null;
    });
    try {
      final dio = ref.read(apiClientProvider).dio;
      if (_isEditing) {
        final resp = await dio.post<dynamic>(
          'staff/menu/${widget.dishId}/',
          data: _fieldsBody(),
        );
        final result = parseStaffJson(resp, (d) {
          final body = (d as Map<String, dynamic>)['dish'] as Map<String, dynamic>;
          return (DishDetail.fromJson(body), body);
        });
        setState(() => _applyDish(result.$1, result.$2));
        ref.invalidate(staffMenuListProvider);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Dish saved.')));
      } else {
        final body = _fieldsBody()..['slug'] = _slugController.text.trim();
        final resp = await dio.post<dynamic>('staff/menu/new/', data: body);
        parseStaffJson(resp, (d) => d);
        ref.invalidate(staffMenuListProvider);
        if (!mounted) return;
        Navigator.of(context).pop();
      }
    } on ApiException catch (e) {
      _showError(e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _reloadDish() async {
    if (!_isEditing) return;
    try {
      final resp = await ref.read(apiClientProvider).dio.get<dynamic>('staff/menu/${widget.dishId}/');
      final result = parseStaffJson(resp, (d) {
        final body = (d as Map<String, dynamic>)['dish'] as Map<String, dynamic>;
        return (DishDetail.fromJson(body), body);
      });
      if (mounted) setState(() => _applyDish(result.$1, result.$2));
    } on ApiException catch (e) {
      _showError(e);
    }
  }

  Future<void> _pickAndUploadImage() async {
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
    if (source == null) return;
    final picked = await ImagePicker().pickImage(source: source);
    if (picked == null) return;

    setState(() => _uploadingImage = true);
    try {
      final formData = FormData.fromMap({
        'image': await MultipartFile.fromFile(picked.path),
      });
      final resp = await ref
          .read(apiClientProvider)
          .dio
          .post<dynamic>('staff/menu/${widget.dishId}/image/', data: formData);
      parseStaffJson(resp, (d) => d);
      await _reloadDish();
    } on ApiException catch (e) {
      _showError(e);
    } finally {
      if (mounted) setState(() => _uploadingImage = false);
    }
  }

  Future<void> _addOption() async {
    final name = _newOptionNameController.text.trim();
    if (name.isEmpty) return;
    try {
      final resp = await ref.read(apiClientProvider).dio.post<dynamic>(
        'staff/menu/${widget.dishId}/options/',
        data: {
          'name': name,
          'required': _newOptionRequired,
          'sort_order': int.tryParse(_newOptionSortController.text.trim()) ?? 0,
        },
      );
      parseStaffJson(resp, (d) => d);
      _newOptionNameController.clear();
      _newOptionSortController.text = '0';
      await _reloadDish();
    } on ApiException catch (e) {
      _showError(e);
    }
  }

  Future<void> _deleteOption(DishOption option) async {
    final confirmed = await _confirm(
      title: 'Remove option',
      message: 'Remove "${option.name}" and all its values?',
    );
    if (confirmed != true) return;
    try {
      final resp = await ref
          .read(apiClientProvider)
          .dio
          .delete<dynamic>('staff/menu/${widget.dishId}/options/${option.id}/');
      parseStaffJson(resp, (d) => d);
      await _reloadDish();
    } on ApiException catch (e) {
      _showError(e);
    }
  }

  Future<void> _addValue(DishOption option, String name, String priceDeltaText) async {
    if (name.trim().isEmpty) return;
    try {
      final resp = await ref.read(apiClientProvider).dio.post<dynamic>(
        'staff/menu/${widget.dishId}/options/${option.id}/values/',
        data: {
          'name': name.trim(),
          'price_delta_cents': int.tryParse(priceDeltaText.trim()) ?? 0,
          'sort_order': 0,
        },
      );
      parseStaffJson(resp, (d) => d);
      await _reloadDish();
    } on ApiException catch (e) {
      _showError(e);
    }
  }

  Future<void> _deleteValue(DishOption option, DishOptionValue value) async {
    final confirmed = await _confirm(
      title: 'Remove value',
      message: 'Remove "${value.name}"?',
    );
    if (confirmed != true) return;
    try {
      final resp = await ref.read(apiClientProvider).dio.delete<dynamic>(
        'staff/menu/${widget.dishId}/options/${option.id}/values/${value.id}/',
      );
      parseStaffJson(resp, (d) => d);
      await _reloadDish();
    } on ApiException catch (e) {
      _showError(e);
    }
  }

  Future<void> _toggleValueAvailable(DishOption option, DishOptionValue value) async {
    try {
      final resp = await ref.read(apiClientProvider).dio.post<dynamic>(
        'staff/menu/${widget.dishId}/options/${option.id}/values/${value.id}/',
        data: {
          'name': value.name,
          'price_delta_cents': value.priceDeltaCents,
          'sort_order': value.sortOrder,
          'is_available': !value.isAvailable,
        },
      );
      parseStaffJson(resp, (d) => d);
      await _reloadDish();
    } on ApiException catch (e) {
      _showError(e);
    }
  }

  Future<bool?> _confirm({required String title, required String message}) {
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Remove')),
        ],
      ),
    );
  }

  Future<void> _archive() async {
    final confirmed = await _confirm(
      title: 'Archive dish',
      message: 'Archive "${_dish?.name}"? It will disappear from the public menu.',
    );
    if (confirmed != true) return;
    await _postArchive(confirm: false);
  }

  Future<void> _postArchive({required bool confirm}) async {
    try {
      final resp = await ref.read(apiClientProvider).dio.post<dynamic>(
        'staff/menu/${widget.dishId}/archive/',
        data: {'confirm': confirm},
      );
      final status = resp.statusCode ?? 0;
      if (status >= 200 && status < 300) {
        final body = (resp.data as Map<String, dynamic>)['dish'] as Map<String, dynamic>;
        setState(() => _applyDish(DishDetail.fromJson(body), body));
        ref.invalidate(staffMenuListProvider);
        return;
      }
      final data = resp.data is Map<String, dynamic> ? resp.data as Map<String, dynamic> : null;
      final affected = data?['affected_order_count'] as int?;
      final message = (data?['message'] as String?) ?? 'Something went wrong.';
      if (affected != null && affected > 0) {
        final reconfirmed = await _confirmAffectedOrders(affected);
        if (reconfirmed == true) await _postArchive(confirm: true);
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Something went wrong.')));
      }
    }
  }

  Future<bool?> _confirmAffectedOrders(int count) {
    var understood = false;
    return showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('This dish has active orders'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '$count occupying order${count == 1 ? '' : 's'} reference this dish. '
                'Those orders keep their own name/price snapshot, so archiving is safe, '
                'but it will disappear from the menu immediately.',
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Checkbox(
                    value: understood,
                    onChanged: (v) => setDialogState(() => understood = v ?? false),
                  ),
                  const Expanded(child: Text('I understand, archive it anyway.')),
                ],
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            TextButton(
              onPressed: understood ? () => Navigator.pop(ctx, true) : null,
              child: const Text('Archive'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _unarchive() async {
    try {
      final resp = await ref
          .read(apiClientProvider)
          .dio
          .post<dynamic>('staff/menu/${widget.dishId}/unarchive/');
      final body = parseStaffJson(
        resp,
        (d) => (d as Map<String, dynamic>)['dish'] as Map<String, dynamic>,
      );
      setState(() => _applyDish(DishDetail.fromJson(body), body));
      ref.invalidate(staffMenuListProvider);
    } on ApiException catch (e) {
      _showError(e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StaffScaffold(
      title: _isEditing ? 'Edit dish' : 'New dish',
      body: FutureBuilder<void>(
        future: _loadFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
                child: Text('Could not load: ${snapshot.error}', style: PosterText.bodyDefault),
              ),
            );
          }
          return SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(
              PosterSpace.pageSidePadding, 16, PosterSpace.pageSidePadding,
              PosterSpace.bottomPagePadding,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_isEditing) ...[
                  _ImageSection(
                    photoUrl: _dish?.photoUrl ?? '',
                    uploading: _uploadingImage,
                    onChangePhoto: _pickAndUploadImage,
                  ),
                  const SizedBox(height: 20),
                ],
                if (!_isEditing) ...[
                  _field('Slug', _slugController, helper: 'Lowercase, hyphens only — permanent.'),
                  const SizedBox(height: 12),
                ],
                _field('Name', _nameController, error: _fieldErrors?['name']),
                const SizedBox(height: 12),
                _field(
                  'Price (R)',
                  _priceController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  error: _fieldErrors?['price_cents'],
                ),
                const SizedBox(height: 12),
                _field('Portion label', _portionController),
                const SizedBox(height: 12),
                _field('Short description', _shortDescController, maxLines: 2),
                const SizedBox(height: 12),
                _field('Long description', _longDescController, maxLines: 4),
                const SizedBox(height: 12),
                _field('Spice default', _spiceController),
                const SizedBox(height: 12),
                _field('Allergen text', _allergenController, maxLines: 2),
                const SizedBox(height: 12),
                _field(
                  'Dietary tags (comma separated)', _dietaryTagsController,
                  helper: 'e.g. vegetarian, halal',
                ),
                const SizedBox(height: 12),
                _field('Category', _categoryController, error: _fieldErrors?['category']),
                if (!_isEditing && _categorySuggestions.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Wrap(
                      spacing: 6,
                      children: [
                        for (final c in _categorySuggestions)
                          ActionChip(
                            label: Text(c, style: PosterText.bodyDefault),
                            onPressed: () => _categoryController.text = c,
                          ),
                      ],
                    ),
                  ),
                const SizedBox(height: 12),
                _field(
                  'Sort order', _sortOrderController,
                  keyboardType: TextInputType.number,
                ),
                const SizedBox(height: 8),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Active on menu'),
                  value: _isActiveOnMenu,
                  onChanged: (v) => setState(() => _isActiveOnMenu = v),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Allow order notes'),
                  value: _allowNotes,
                  onChanged: (v) => setState(() => _allowNotes = v),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Featured on homepage'),
                  subtitle: const Text('Un-features whichever other dish currently has this.'),
                  value: _isFeatured,
                  onChanged: (v) => setState(() => _isFeatured = v),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _saving ? null : _save,
                    style: FilledButton.styleFrom(backgroundColor: PosterColors.navy),
                    child: _saving
                        ? const SizedBox(
                            height: 18, width: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: PosterColors.white),
                          )
                        : Text(_isEditing ? 'Save' : 'Create dish'),
                  ),
                ),
                if (_isEditing) ...[
                  const SizedBox(height: 28),
                  Text('Options', style: PosterText.cardTitle.copyWith(fontSize: 18)),
                  const SizedBox(height: 8),
                  for (final option in _options)
                    _OptionCard(
                      option: option,
                      onDeleteOption: () => _deleteOption(option),
                      onDeleteValue: (v) => _deleteValue(option, v),
                      onToggleValue: (v) => _toggleValueAvailable(option, v),
                      onAddValue: (name, priceDelta) => _addValue(option, name, priceDelta),
                    ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      border: Border.all(color: PosterColors.border),
                      borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Add option', style: PosterText.bodyLarge.copyWith(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 8),
                        TextField(
                          controller: _newOptionNameController,
                          decoration: const InputDecoration(labelText: 'Option name'),
                        ),
                        Row(
                          children: [
                            Expanded(
                              child: SwitchListTile(
                                contentPadding: EdgeInsets.zero,
                                title: const Text('Required'),
                                value: _newOptionRequired,
                                onChanged: (v) => setState(() => _newOptionRequired = v),
                              ),
                            ),
                            SizedBox(
                              width: 80,
                              child: TextField(
                                controller: _newOptionSortController,
                                keyboardType: TextInputType.number,
                                decoration: const InputDecoration(labelText: 'Order'),
                              ),
                            ),
                          ],
                        ),
                        Align(
                          alignment: Alignment.centerRight,
                          child: TextButton(onPressed: _addOption, child: const Text('Add option')),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 28),
                  Text(
                    _dish?.isArchived == true ? 'This dish is archived' : 'Archive',
                    style: PosterText.cardTitle.copyWith(fontSize: 18),
                  ),
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton(
                      onPressed: _dish?.isArchived == true ? _unarchive : _archive,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: PosterColors.error,
                        side: const BorderSide(color: PosterColors.error),
                      ),
                      child: Text(_dish?.isArchived == true ? 'Unarchive' : 'Archive dish'),
                    ),
                  ),
                ],
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _field(
    String label,
    TextEditingController controller, {
    int maxLines = 1,
    TextInputType? keyboardType,
    String? helper,
    String? error,
  }) {
    return TextField(
      controller: controller,
      maxLines: maxLines,
      keyboardType: keyboardType,
      decoration: InputDecoration(
        labelText: label,
        helperText: helper,
        errorText: error,
      ),
    );
  }
}

class _ImageSection extends StatelessWidget {
  const _ImageSection({
    required this.photoUrl,
    required this.uploading,
    required this.onChangePhoto,
  });

  final String photoUrl;
  final bool uploading;
  final VoidCallback onChangePhoto;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
          child: Container(
            width: 84, height: 84,
            color: PosterColors.border,
            child: photoUrl.isEmpty
                ? const Icon(Icons.restaurant_menu_rounded, color: PosterColors.muted)
                : Image.network(photoUrl, fit: BoxFit.cover),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: OutlinedButton(
            onPressed: uploading ? null : onChangePhoto,
            child: uploading
                ? const SizedBox(
                    height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Change photo'),
          ),
        ),
      ],
    );
  }
}

class _OptionCard extends StatefulWidget {
  const _OptionCard({
    required this.option,
    required this.onDeleteOption,
    required this.onDeleteValue,
    required this.onToggleValue,
    required this.onAddValue,
  });

  final DishOption option;
  final VoidCallback onDeleteOption;
  final void Function(DishOptionValue value) onDeleteValue;
  final void Function(DishOptionValue value) onToggleValue;
  final void Function(String name, String priceDeltaCents) onAddValue;

  @override
  State<_OptionCard> createState() => _OptionCardState();
}

class _OptionCardState extends State<_OptionCard> {
  final _nameController = TextEditingController();
  final _priceController = TextEditingController(text: '0');

  @override
  void dispose() {
    _nameController.dispose();
    _priceController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final option = widget.option;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: PosterColors.border),
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '${option.name}${option.required ? ' (required)' : ''}',
                  style: PosterText.bodyLarge.copyWith(fontWeight: FontWeight.w700),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline, color: PosterColors.error),
                onPressed: widget.onDeleteOption,
              ),
            ],
          ),
          for (final value in option.values)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      '${value.name}'
                      '${value.priceDeltaCents == 0 ? '' : ' (${_signedRand(value.priceDeltaCents)})'}',
                      style: PosterText.bodyDefault,
                    ),
                  ),
                  Switch(
                    value: value.isAvailable,
                    onChanged: (_) => widget.onToggleValue(value),
                  ),
                  IconButton(
                    iconSize: 18,
                    icon: const Icon(Icons.close, color: PosterColors.muted),
                    onPressed: () => widget.onDeleteValue(value),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 6),
          Row(
            children: [
              Expanded(
                flex: 2,
                child: TextField(
                  controller: _nameController,
                  decoration: const InputDecoration(labelText: 'Value name', isDense: true),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _priceController,
                  keyboardType: const TextInputType.numberWithOptions(signed: true),
                  decoration: const InputDecoration(labelText: 'Δ cents', isDense: true),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.add_circle_outline),
                onPressed: () {
                  widget.onAddValue(_nameController.text, _priceController.text);
                  _nameController.clear();
                  _priceController.text = '0';
                },
              ),
            ],
          ),
        ],
      ),
    );
  }
}
