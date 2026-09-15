import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api_exception.dart';
import '../../../data/staff/staff_api.dart';
import '../../../state/api_providers.dart';
import '../../../state/staff_auth.dart';
import '../../../theme/poster_tokens.dart';
import '../staff_scaffold.dart';

const _roles = ['manager', 'owner', 'admin'];

String _roleLabel(String role) => switch (role) {
      'admin' => 'Admin',
      'owner' => 'Owner',
      _ => 'Manager',
    };

/// Team — the admin-only staff allowlist manager. Backend:
/// `GET/POST /api/v1/staff/team/` (invite) + `POST`/`DELETE
/// /api/v1/staff/team/:id/` (change role / remove)
/// (`staff/api_mobile_admin.py::team_json`/`team_member_json`, mirroring
/// `staff/views.py::team`).
class TeamScreen extends ConsumerStatefulWidget {
  const TeamScreen({super.key});

  @override
  ConsumerState<TeamScreen> createState() => _TeamScreenState();
}

class _TeamScreenState extends ConsumerState<TeamScreen> {
  Future<List<TeamMember>>? _future;

  @override
  void initState() {
    super.initState();
    final user = ref.read(staffAuthProvider).user;
    if (user != null && user.isAdmin) {
      _future = _load();
    }
  }

  Future<List<TeamMember>> _load() async {
    final dio = ref.read(apiClientProvider).dio;
    final resp = await dio.get<dynamic>('staff/team/');
    return parseStaffJson(resp, (d) {
      final rows = (d as Map<String, dynamic>)['team'] as List<dynamic>;
      return rows.map((e) => TeamMember.fromJson(e as Map<String, dynamic>)).toList();
    });
  }

  Future<void> _refresh() async {
    final next = _load();
    setState(() => _future = next);
    await next;
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(staffAuthProvider).user;
    if (user == null || !user.isAdmin) {
      return const StaffScaffold(
        title: 'Team',
        body: Center(child: Text('You don\'t have access to Team.')),
      );
    }

    return StaffScaffold(
      title: 'Team',
      body: FutureBuilder<List<TeamMember>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            final message =
                snapshot.error is ApiException ? (snapshot.error! as ApiException).message : 'Could not load the team.';
            return RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(32),
                children: [
                  const SizedBox(height: 80),
                  Text(message, textAlign: TextAlign.center, style: PosterText.bodyLarge),
                ],
              ),
            );
          }
          final rows = snapshot.data!;
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(
                PosterSpace.pageSidePadding, 16, PosterSpace.pageSidePadding, PosterSpace.bottomPagePadding,
              ),
              children: [
                _InviteCard(onInvited: _refresh),
                const SizedBox(height: 8),
                Text('TEAM (${rows.length})', style: PosterText.eyebrow.copyWith(color: PosterColors.navy)),
                const SizedBox(height: 8),
                for (final row in rows)
                  _TeamMemberCard(
                    row: row,
                    isSelf: row.email.toLowerCase() == user.email.toLowerCase(),
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

class _InviteCard extends ConsumerStatefulWidget {
  const _InviteCard({required this.onInvited});

  final Future<void> Function() onInvited;

  @override
  ConsumerState<_InviteCard> createState() => _InviteCardState();
}

class _InviteCardState extends ConsumerState<_InviteCard> {
  final _emailController = TextEditingController();
  String _role = 'manager';
  bool _submitting = false;

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _invite() async {
    final email = _emailController.text.trim();
    if (email.isEmpty) return;
    setState(() => _submitting = true);
    try {
      final dio = ref.read(apiClientProvider).dio;
      final resp = await dio.post<dynamic>('staff/team/', data: {'email': email, 'role': _role});
      final alreadyExisted =
          parseStaffJson(resp, (d) => (d as Map<String, dynamic>)['already_existed'] as bool? ?? false);
      _emailController.clear();
      await widget.onInvited();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(alreadyExisted ? '$email is already on the allowlist.' : 'Added $email to the team.'),
            backgroundColor: alreadyExisted ? PosterColors.bluePanel : PosterColors.success,
          ),
        );
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message), backgroundColor: PosterColors.error));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: PosterColors.white,
        border: Border.all(color: PosterColors.border, width: 1.5),
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('INVITE', style: PosterText.eyebrow.copyWith(color: PosterColors.navy)),
          const SizedBox(height: 12),
          TextField(
            controller: _emailController,
            keyboardType: TextInputType.emailAddress,
            decoration: InputDecoration(
              labelText: 'Email',
              filled: true,
              fillColor: PosterColors.paper,
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(PosterSpace.radiusInput)),
            ),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            initialValue: _role,
            decoration: InputDecoration(
              labelText: 'Role',
              filled: true,
              fillColor: PosterColors.paper,
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(PosterSpace.radiusInput)),
            ),
            items: [for (final r in _roles) DropdownMenuItem(value: r, child: Text(_roleLabel(r)))],
            onChanged: (v) {
              if (v != null) setState(() => _role = v);
            },
          ),
          const SizedBox(height: 12),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: PosterColors.gold,
              foregroundColor: PosterColors.navy,
              minimumSize: const Size.fromHeight(44),
            ),
            onPressed: _submitting ? null : _invite,
            child: _submitting
                ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('INVITE', style: PosterText.button),
          ),
        ],
      ),
    );
  }
}

class _TeamMemberCard extends ConsumerStatefulWidget {
  const _TeamMemberCard({required this.row, required this.isSelf, required this.onChanged});

  final TeamMember row;
  final bool isSelf;
  final Future<void> Function() onChanged;

  @override
  ConsumerState<_TeamMemberCard> createState() => _TeamMemberCardState();
}

class _TeamMemberCardState extends ConsumerState<_TeamMemberCard> {
  bool _busy = false;

  Future<void> _changeRole(String role) async {
    if (role == widget.row.role || _busy) return;
    setState(() => _busy = true);
    try {
      final dio = ref.read(apiClientProvider).dio;
      final resp = await dio.post<dynamic>('staff/team/${widget.row.allowlistId}/', data: {'role': role});
      parseStaffJson(resp, (d) => d);
      await widget.onChanged();
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message), backgroundColor: PosterColors.error));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _remove() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove team member'),
        content: const Text('Remove this person from the team? They will not be able to sign in as staff.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: PosterColors.error),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _busy = true);
    try {
      final dio = ref.read(apiClientProvider).dio;
      final resp = await dio.delete<dynamic>('staff/team/${widget.row.allowlistId}/');
      parseStaffJson(resp, (d) => d);
      await widget.onChanged();
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message), backgroundColor: PosterColors.error));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final row = widget.row;
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
                child: Text(
                  row.email,
                  style: PosterText.bodyLarge.copyWith(color: PosterColors.navy, fontWeight: FontWeight.w700),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (widget.isSelf)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: PosterColors.bluePanel,
                    borderRadius: BorderRadius.circular(PosterSpace.radiusButton),
                  ),
                  child: Text('YOU', style: PosterText.bodyDefault.copyWith(color: PosterColors.white, fontSize: 11)),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 12,
            runSpacing: 4,
            children: [
              _Indicator(
                icon: row.hasLiveAccount ? Icons.check_circle_rounded : Icons.cancel_outlined,
                color: row.hasLiveAccount ? PosterColors.success : PosterColors.muted,
                label: row.hasLiveAccount ? 'Live account' : 'No account yet',
              ),
              _Indicator(
                icon: row.signedInViaGoogle ? Icons.check_circle_rounded : Icons.cancel_outlined,
                color: row.signedInViaGoogle ? PosterColors.success : PosterColors.muted,
                label: row.signedInViaGoogle ? 'Google sign-in' : 'No Google sign-in',
              ),
            ],
          ),
          if (row.invitedByName != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                'Invited by ${row.invitedByName}',
                style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
              ),
            ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String>(
                  initialValue: row.role,
                  isDense: true,
                  decoration: InputDecoration(
                    labelText: 'Role',
                    filled: true,
                    fillColor: PosterColors.paper,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(PosterSpace.radiusInput)),
                  ),
                  items: [for (final r in _roles) DropdownMenuItem(value: r, child: Text(_roleLabel(r)))],
                  onChanged: _busy ? null : (v) => v == null ? null : _changeRole(v),
                ),
              ),
              const SizedBox(width: 8),
              if (!widget.isSelf)
                IconButton(
                  onPressed: _busy ? null : _remove,
                  icon: const Icon(Icons.delete_outline_rounded, color: PosterColors.error),
                  tooltip: 'Remove',
                ),
              if (_busy) const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2)),
            ],
          ),
        ],
      ),
    );
  }
}

class _Indicator extends StatelessWidget {
  const _Indicator({required this.icon, required this.color, required this.label});

  final IconData icon;
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: color),
        const SizedBox(width: 4),
        Text(label, style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
      ],
    );
  }
}

class TeamMember {
  const TeamMember({
    required this.allowlistId,
    required this.email,
    required this.role,
    required this.hasLiveAccount,
    required this.signedInViaGoogle,
    required this.invitedByName,
  });

  factory TeamMember.fromJson(Map<String, dynamic> json) => TeamMember(
        allowlistId: json['allowlist_id'] as int,
        email: json['email'] as String,
        role: json['role'] as String,
        hasLiveAccount: json['has_live_account'] as bool? ?? false,
        signedInViaGoogle: json['signed_in_via_google'] as bool? ?? false,
        invitedByName: json['invited_by_name'] as String?,
      );

  final int allowlistId;
  final String email;
  final String role;
  final bool hasLiveAccount;
  final bool signedInViaGoogle;
  final String? invitedByName;
}
