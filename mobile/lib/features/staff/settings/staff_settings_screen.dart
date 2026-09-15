import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api_exception.dart';
import '../../../data/staff/staff_api.dart';
import '../../../state/api_providers.dart';
import '../../../state/staff_auth.dart';
import '../../../theme/poster_tokens.dart';
import '../staff_scaffold.dart';

/// Settings — the owner/admin-only singleton `core.models.Settings` row
/// editor (§7.2, D-24). Backend: `GET/POST /api/v1/staff/settings/`
/// (`staff/api_mobile_admin.py::settings_json`, itself mirroring
/// `staff/views.py::settings_view` + `SettingsForm`'s field list).
///
/// The whole form is always sent back on Save (never a partial diff) so
/// the model's own `CheckConstraint`s (window-before-cutoff, etc.) are
/// checked against a complete row the same way the web `ModelForm` does
/// — a validation failure comes back as one message, shown as a banner
/// at the top of the form; nothing the user typed is lost.
class StaffSettingsScreen extends ConsumerStatefulWidget {
  const StaffSettingsScreen({super.key});

  @override
  ConsumerState<StaffSettingsScreen> createState() => _StaffSettingsScreenState();
}

enum _FieldKind { text, multiline, intField, time, boolField }

class _FieldSpec {
  const _FieldSpec(this.key, this.label, this.kind, {this.hint, this.required = false});
  final String key;
  final String label;
  final _FieldKind kind;
  final String? hint;
  final bool required;
}

class _SectionSpec {
  const _SectionSpec(this.title, this.fields);
  final String title;
  final List<_FieldSpec> fields;
}

const _sections = <_SectionSpec>[
  _SectionSpec('Business info', [
    _FieldSpec('public_site_name', 'Public site name', _FieldKind.text, required: true),
    _FieldSpec('collection_address_line', 'Collection address', _FieldKind.multiline),
    _FieldSpec('collection_instructions', 'Collection instructions', _FieldKind.multiline),
  ]),
  _SectionSpec('Bank details', [
    _FieldSpec('bank_name', 'Bank name', _FieldKind.text),
    _FieldSpec('account_name', 'Account name', _FieldKind.text),
    _FieldSpec('account_number', 'Account number', _FieldKind.text, hint: '6-20 digits'),
    _FieldSpec('branch_code', 'Branch code', _FieldKind.text),
    _FieldSpec('account_type', 'Account type', _FieldKind.text),
  ]),
  _SectionSpec('Timing & capacity', [
    _FieldSpec('default_window_start', 'Default window start', _FieldKind.time, required: true),
    _FieldSpec('default_window_end', 'Default window end', _FieldKind.time, required: true),
    _FieldSpec('same_day_cutoff', 'Same-day cutoff', _FieldKind.time, required: true),
    _FieldSpec('slot_minutes', 'Slot length (minutes)', _FieldKind.intField, required: true),
    _FieldSpec('default_slot_capacity', 'Default slot capacity', _FieldKind.intField, required: true),
    _FieldSpec('default_daily_order_cap', 'Default daily order cap', _FieldKind.intField, required: true),
    _FieldSpec('preorder_days', 'Preorder days', _FieldKind.intField, required: true),
  ]),
  _SectionSpec('EFT', [
    _FieldSpec('eft_hold_minutes', 'EFT hold minutes', _FieldKind.intField, required: true),
    _FieldSpec('max_hold_extensions', 'Max hold extensions', _FieldKind.intField, required: true),
    _FieldSpec('hold_extension_minutes', 'Hold extension minutes', _FieldKind.intField, required: true),
    _FieldSpec('payment_review_sla_minutes', 'Payment review SLA (minutes)', _FieldKind.intField, required: true),
  ]),
  _SectionSpec('Cash', [
    _FieldSpec('cash_enabled', 'Cash accepted', _FieldKind.boolField),
    _FieldSpec('cash_same_day_only', 'Cash same-day only', _FieldKind.boolField),
    _FieldSpec('cash_daily_cap', 'Cash daily cap', _FieldKind.intField, required: true),
  ]),
  _SectionSpec('Collection', [
    _FieldSpec('collection_grace_minutes', 'Collection grace minutes', _FieldKind.intField, required: true),
    _FieldSpec('assisted_after_cutoff_enabled', 'Assisted orders after cutoff', _FieldKind.boolField),
    _FieldSpec('support_whatsapp_e164', 'Support WhatsApp number', _FieldKind.text, hint: '+27...'),
  ]),
  _SectionSpec('Compliance / VAT', [
    _FieldSpec('allergen_disclaimer', 'Allergen disclaimer', _FieldKind.multiline),
    _FieldSpec('home_kitchen_notice', 'Home kitchen notice', _FieldKind.multiline),
    _FieldSpec('vat_registered', 'VAT registered', _FieldKind.boolField),
    _FieldSpec('vat_number', 'VAT number', _FieldKind.text),
  ]),
  _SectionSpec('Retention', [
    _FieldSpec('proof_retention_days', 'Proof retention (days)', _FieldKind.intField, required: true),
    _FieldSpec('order_retention_months', 'Order retention (months)', _FieldKind.intField, required: true),
  ]),
  _SectionSpec('SMS', [
    _FieldSpec('sms_enabled', 'SMS ready notifications', _FieldKind.boolField),
    _FieldSpec('sms_ready_template', 'SMS ready template', _FieldKind.multiline),
  ]),
];

class _StaffSettingsScreenState extends ConsumerState<StaffSettingsScreen> {
  Future<void>? _loadFuture;
  final Map<String, TextEditingController> _text = {};
  final Map<String, bool> _bools = {};
  final Map<String, String?> _times = {}; // "HH:MM:SS" as returned by the API
  bool _saving = false;
  String? _errorBanner;

  @override
  void initState() {
    super.initState();
    final user = ref.read(staffAuthProvider).user;
    if (user != null && user.isOwnerOrAdmin) {
      _loadFuture = _load();
    }
  }

  @override
  void dispose() {
    for (final c in _text.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    final dio = ref.read(apiClientProvider).dio;
    final resp = await dio.get<dynamic>('staff/settings/');
    final settings = parseStaffJson(resp, (d) => (d as Map<String, dynamic>)['settings'] as Map<String, dynamic>);
    _applySettings(settings);
  }

  void _applySettings(Map<String, dynamic> settings) {
    for (final section in _sections) {
      for (final field in section.fields) {
        final value = settings[field.key];
        switch (field.kind) {
          case _FieldKind.boolField:
            _bools[field.key] = value == true;
          case _FieldKind.time:
            _times[field.key] = value as String?;
          case _FieldKind.text:
          case _FieldKind.multiline:
          case _FieldKind.intField:
            final controller = _text.putIfAbsent(field.key, TextEditingController.new);
            controller.text = value == null ? '' : value.toString();
        }
      }
    }
  }

  void setBool(String key, bool value) => setState(() => _bools[key] = value);

  void setTime(String key, String value) => setState(() => _times[key] = value);

  Object? _valueFor(_FieldSpec field) {
    switch (field.kind) {
      case _FieldKind.boolField:
        return _bools[field.key] ?? false;
      case _FieldKind.time:
        return _times[field.key];
      case _FieldKind.intField:
        final text = _text[field.key]?.text.trim() ?? '';
        return text.isEmpty ? null : int.tryParse(text);
      case _FieldKind.text:
      case _FieldKind.multiline:
        final text = _text[field.key]?.text.trim() ?? '';
        if (text.isEmpty && !field.required) return null;
        return text;
    }
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _errorBanner = null;
    });
    final body = <String, Object?>{
      for (final section in _sections)
        for (final field in section.fields) field.key: _valueFor(field),
    };
    try {
      final dio = ref.read(apiClientProvider).dio;
      final resp = await dio.post<dynamic>('staff/settings/', data: body);
      final settings = parseStaffJson(resp, (d) => (d as Map<String, dynamic>)['settings'] as Map<String, dynamic>);
      _applySettings(settings);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Settings saved.'), backgroundColor: PosterColors.success),
        );
      }
    } on ApiException catch (e) {
      setState(() => _errorBanner = e.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(staffAuthProvider).user;
    if (user == null || !user.isOwnerOrAdmin) {
      return const StaffScaffold(
        title: 'Settings',
        body: Center(child: Text('You don\'t have access to Settings.')),
      );
    }

    return StaffScaffold(
      title: 'Settings',
      body: FutureBuilder<void>(
        future: _loadFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            final message =
                snapshot.error is ApiException ? (snapshot.error! as ApiException).message : 'Could not load settings.';
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Text(message, textAlign: TextAlign.center, style: PosterText.bodyLarge),
              ),
            );
          }
          return ListView(
            padding: const EdgeInsets.fromLTRB(
              PosterSpace.pageSidePadding, 16, PosterSpace.pageSidePadding, PosterSpace.bottomPagePadding,
            ),
            children: [
              if (_errorBanner != null)
                Container(
                  margin: const EdgeInsets.only(bottom: 16),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: PosterColors.error.withValues(alpha: 0.1),
                    border: Border.all(color: PosterColors.error, width: 1.5),
                    borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
                  ),
                  child: Text(_errorBanner!, style: PosterText.bodyDefault.copyWith(color: PosterColors.error)),
                ),
              for (final section in _sections) _SettingsSection(section: section, state: this),
              const SizedBox(height: 8),
              FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: PosterColors.gold,
                  foregroundColor: PosterColors.navy,
                  minimumSize: const Size.fromHeight(48),
                ),
                onPressed: _saving ? null : _save,
                child: _saving
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('SAVE', style: PosterText.button),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _SettingsSection extends StatelessWidget {
  const _SettingsSection({required this.section, required this.state});

  final _SectionSpec section;
  final _StaffSettingsScreenState state;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: PosterColors.white,
        border: Border.all(color: PosterColors.border, width: 1.5),
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(section.title.toUpperCase(), style: PosterText.eyebrow.copyWith(color: PosterColors.navy)),
          const SizedBox(height: 12),
          for (final field in section.fields) ...[
            _SettingsField(field: field, state: state),
            const SizedBox(height: 12),
          ],
        ],
      ),
    );
  }
}

class _SettingsField extends StatelessWidget {
  const _SettingsField({required this.field, required this.state});

  final _FieldSpec field;
  final _StaffSettingsScreenState state;

  @override
  Widget build(BuildContext context) {
    switch (field.kind) {
      case _FieldKind.boolField:
        return SwitchListTile(
          contentPadding: EdgeInsets.zero,
          value: state._bools[field.key] ?? false,
          activeThumbColor: PosterColors.blue,
          title: Text(field.label, style: PosterText.bodyLarge.copyWith(color: PosterColors.navy)),
          onChanged: (v) => state.setBool(field.key, v),
        );
      case _FieldKind.time:
        final raw = state._times[field.key];
        final label = raw == null || raw.isEmpty ? '--:--' : raw.substring(0, 5);
        return InkWell(
          onTap: () async {
            final initial = _parseTime(raw) ?? const TimeOfDay(hour: 12, minute: 0);
            final picked = await showTimePicker(context: context, initialTime: initial);
            if (picked != null) {
              state.setTime(
                field.key,
                '${picked.hour.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')}:00',
              );
            }
          },
          child: InputDecorator(
            decoration: InputDecoration(
              labelText: field.label,
              filled: true,
              fillColor: PosterColors.paper,
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(PosterSpace.radiusInput)),
            ),
            child: Text(label, style: PosterText.bodyLarge.copyWith(color: PosterColors.navy)),
          ),
        );
      case _FieldKind.intField:
        return TextField(
          controller: state._text[field.key],
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          decoration: InputDecoration(
            labelText: field.label,
            hintText: field.hint,
            filled: true,
            fillColor: PosterColors.paper,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(PosterSpace.radiusInput)),
          ),
        );
      case _FieldKind.text:
        return TextField(
          controller: state._text[field.key],
          decoration: InputDecoration(
            labelText: field.label,
            hintText: field.hint,
            filled: true,
            fillColor: PosterColors.paper,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(PosterSpace.radiusInput)),
          ),
        );
      case _FieldKind.multiline:
        return TextField(
          controller: state._text[field.key],
          minLines: 2,
          maxLines: 5,
          decoration: InputDecoration(
            labelText: field.label,
            hintText: field.hint,
            filled: true,
            fillColor: PosterColors.paper,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(PosterSpace.radiusInput)),
          ),
        );
    }
  }

  TimeOfDay? _parseTime(String? raw) {
    if (raw == null || raw.length < 5) return null;
    final hour = int.tryParse(raw.substring(0, 2));
    final minute = int.tryParse(raw.substring(3, 5));
    if (hour == null || minute == null) return null;
    return TimeOfDay(hour: hour, minute: minute);
  }
}
