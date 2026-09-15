import 'package:flutter/material.dart';

import '../../../theme/poster_tokens.dart';
import '../staff_scaffold.dart';
import 'help_content.dart';
import 'help_widgets.dart';

/// One Help section's full content — pushed from [StaffHelpScreen] when a
/// row is tapped. Pure presentation: all copy lives in [HelpSection.blocks]
/// (`help_content.dart`), rendered block-by-block via `buildHelpBlock`
/// (`help_widgets.dart`).
class HelpDetailScreen extends StatelessWidget {
  const HelpDetailScreen({super.key, required this.section});

  final HelpSection section;

  @override
  Widget build(BuildContext context) {
    return StaffScaffold(
      title: section.title,
      body: ListView(
        padding: const EdgeInsets.fromLTRB(
          PosterSpace.pageSidePadding, 16, PosterSpace.pageSidePadding, PosterSpace.bottomPagePadding,
        ),
        children: [
          _DetailHeader(section: section),
          const SizedBox(height: 8),
          for (final block in section.blocks) buildHelpBlock(block),
        ],
      ),
    );
  }
}

class _DetailHeader extends StatelessWidget {
  const _DetailHeader({required this.section});
  final HelpSection section;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PosterColors.navy,
        borderRadius: BorderRadius.circular(10),
        boxShadow: PosterShadows.gold(),
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: const BoxDecoration(color: PosterColors.gold, shape: BoxShape.circle),
            child: Icon(section.icon, color: PosterColors.navy, size: 26),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              section.teaser,
              style: PosterText.bodyDefault.copyWith(color: PosterColors.mutedDark, height: 1.4),
            ),
          ),
        ],
      ),
    );
  }
}
