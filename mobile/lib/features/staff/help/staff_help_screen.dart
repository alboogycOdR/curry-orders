import 'package:flutter/material.dart';

import '../../../theme/poster_tokens.dart';
import '../staff_scaffold.dart';
import 'help_content.dart';
import 'help_detail_screen.dart';

/// Staff Help — the tab's landing/index screen. Fully native, offline
/// content ported from `docs/STAFF_GUIDE.md` (see `help_content.dart` for
/// the actual copy); no more linking out to the website. Tapping a section
/// pushes [HelpDetailScreen] for just that section's content.
class StaffHelpScreen extends StatelessWidget {
  const StaffHelpScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return StaffScaffold(
      title: 'Help',
      body: ListView.builder(
        padding: const EdgeInsets.fromLTRB(
          PosterSpace.pageSidePadding, 16, PosterSpace.pageSidePadding, PosterSpace.bottomPagePadding,
        ),
        itemCount: helpSections.length + 1,
        itemBuilder: (context, index) {
          if (index == 0) return const _IndexIntro();
          return _SectionTile(section: helpSections[index - 1]);
        },
      ),
    );
  }
}

class _IndexIntro extends StatelessWidget {
  const _IndexIntro();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('STAFF GUIDE', style: PosterText.eyebrow.copyWith(color: PosterColors.blue)),
          const SizedBox(height: 6),
          Text(
            'Every screen, in one place',
            style: PosterText.drawerTitle.copyWith(color: PosterColors.navy, fontSize: 26),
          ),
          const SizedBox(height: 6),
          Text(
            'Tap a section below for the full walkthrough — actions, rules and gotchas, '
            'right on your phone.',
            style: PosterText.bodyDefault.copyWith(color: PosterColors.muted, height: 1.4),
          ),
        ],
      ),
    );
  }
}

class _SectionTile extends StatelessWidget {
  const _SectionTile({required this.section});
  final HelpSection section;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: PosterColors.white,
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
        child: InkWell(
          borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => HelpDetailScreen(section: section)),
          ),
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              border: Border.all(color: PosterColors.border),
              borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
            ),
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: const BoxDecoration(color: PosterColors.navy, shape: BoxShape.circle),
                  child: Icon(section.icon, color: PosterColors.goldSoft, size: 22),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        section.title,
                        style: PosterText.bodyLarge.copyWith(
                          color: PosterColors.navy,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        section.teaser,
                        style: PosterText.bodyDefault.copyWith(color: PosterColors.muted, height: 1.3),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 6),
                const Icon(Icons.chevron_right_rounded, color: PosterColors.muted),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
