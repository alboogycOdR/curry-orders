import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../theme/poster_tokens.dart';
import '../staff_scaffold.dart';

/// Staff Help (docs/mobile/FLUTTER_APP_PLAN.md Phase 6). No backend JSON
/// at all -- the staff guide already exists as a live, always-current web
/// page (`https://roticonnect.duckdns.org/manage/help/`) with stable
/// per-section anchor ids (`src/templates/staff/help.html` /
/// `docs/STAFF_GUIDE.md`). This screen is just a native list of section
/// links that open that page (at the matching anchor) in the device
/// browser -- avoids re-porting/duplicating 600+ lines of guide content
/// that would drift out of sync with the source.
class StaffHelpScreen extends StatelessWidget {
  const StaffHelpScreen({super.key});

  static const _baseUrl = 'https://roticonnect.duckdns.org/manage/help/';

  // Label + anchor id, taken verbatim from the guide's own table of
  // contents -- these ids are already stable and used elsewhere in the
  // codebase, do not invent new ones.
  static const _sections = <(String, String)>[
    ('Getting in', 'getting-in'),
    ('Inbox', 'inbox'),
    ('Calendar', 'calendar'),
    ('Kitchen desk', 'kitchen-desk'),
    ('Collection', 'collection'),
    ('Payments', 'payments'),
    ('Cash', 'cash'),
    ('Daily controls', 'daily-controls'),
    ('Menu editor', 'menu-editor'),
    ('New assisted order', 'new-assisted-order'),
    ('Other screens', 'other-screens'),
    ('Roles', 'roles'),
    ('Order flow (EFT)', 'order-flow-eft'),
    ('Order flow (Cash)', 'order-flow-cash'),
    ('Quick reference', 'quick-reference'),
    ('Troubleshooting', 'troubleshooting'),
  ];

  Future<void> _open(BuildContext context, String anchor) async {
    final uri = Uri.parse('$_baseUrl#$anchor');
    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't open the help page.")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return StaffScaffold(
      title: 'Help',
      body: ListView.separated(
        padding: const EdgeInsets.symmetric(
          horizontal: PosterSpace.pageSidePadding,
          vertical: 12,
        ),
        itemCount: _sections.length,
        separatorBuilder: (context, index) => const Divider(height: 1, color: PosterColors.border),
        itemBuilder: (context, index) {
          final (label, anchor) = _sections[index];
          return ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(
              label,
              style: PosterText.bodyLarge.copyWith(color: PosterColors.navy, fontWeight: FontWeight.w600),
            ),
            trailing: const Icon(Icons.open_in_new_rounded, color: PosterColors.muted, size: 20),
            onTap: () => _open(context, anchor),
          );
        },
      ),
    );
  }
}
