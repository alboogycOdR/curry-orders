import 'package:flutter/material.dart';

import '../../../theme/poster_tokens.dart';
import 'help_content.dart';

/// Shared rendering widgets for the Staff Help tab's detail screens — kept
/// separate from `help_content.dart` (plain data) and the screens
/// themselves so each [HelpBlock] variant has exactly one place that knows
/// how to draw it.

/// Splits `text` on `**bold**` markers and renders it as a single
/// [RichText], keeping [base]'s font/size/colour but bumping the weight for
/// the marked spans. Used everywhere guide copy calls out a button, field
/// or status name.
Widget buildRichText(String text, TextStyle base, {Color? color}) {
  final style = base.copyWith(color: color ?? base.color);
  final boldStyle = style.copyWith(fontWeight: FontWeight.w800);
  final parts = text.split('**');
  final spans = <TextSpan>[
    for (var i = 0; i < parts.length; i++)
      if (parts[i].isNotEmpty) TextSpan(text: parts[i], style: i.isOdd ? boldStyle : style),
  ];
  return RichText(text: TextSpan(children: spans));
}

/// Dispatches a single [HelpBlock] to its widget. One `if (block is X)`
/// per block type — new block types plug in here.
Widget buildHelpBlock(HelpBlock block) {
  if (block is HelpHeading) return _HeadingView(block);
  if (block is HelpParagraph) return _ParagraphView(block);
  if (block is HelpList) return _ListView(block);
  if (block is HelpCallout) return _CalloutView(block);
  if (block is HelpTable) return _TableView(block);
  if (block is HelpStepFlow) return _StepFlowView(block);
  if (block is HelpRoleList) return _RoleListView(block);
  if (block is HelpFaqList) return _FaqListView(block);
  return const SizedBox.shrink();
}

class _HeadingView extends StatelessWidget {
  const _HeadingView(this.block);
  final HelpHeading block;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 22, bottom: 10),
      child: Row(
        children: [
          Container(width: 4, height: 16, color: PosterColors.gold),
          const SizedBox(width: 8),
          Text(
            block.text.toUpperCase(),
            style: PosterText.eyebrow.copyWith(color: PosterColors.navy),
          ),
        ],
      ),
    );
  }
}

class _ParagraphView extends StatelessWidget {
  const _ParagraphView(this.block);
  final HelpParagraph block;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: buildRichText(
        block.text,
        PosterText.bodyLarge.copyWith(color: PosterColors.navy, height: 1.42),
      ),
    );
  }
}

class _ListView extends StatelessWidget {
  const _ListView(this.block);
  final HelpList block;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (var i = 0; i < block.items.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 22,
                    child: block.numbered
                        ? Text(
                            '${i + 1}.',
                            style: PosterText.bodyLarge.copyWith(
                              color: PosterColors.blue,
                              fontWeight: FontWeight.w800,
                            ),
                          )
                        : const Padding(
                            padding: EdgeInsets.only(top: 6),
                            child: Icon(Icons.circle, size: 6, color: PosterColors.blue),
                          ),
                  ),
                  Expanded(
                    child: buildRichText(
                      block.items[i],
                      PosterText.bodyLarge.copyWith(color: PosterColors.navy, height: 1.4),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _CalloutStyle {
  const _CalloutStyle(this.color, this.background, this.icon, this.defaultTitle);
  final Color color;
  final Color background;
  final IconData icon;
  final String defaultTitle;
}

const _calloutStyles = <HelpCalloutKind, _CalloutStyle>{
  HelpCalloutKind.info: _CalloutStyle(PosterColors.blue, Color(0x14168CFF), Icons.info_rounded, 'Good to know'),
  HelpCalloutKind.warning: _CalloutStyle(
    PosterColors.gold, Color(0x1FFFC400), Icons.warning_amber_rounded, 'Careful',
  ),
  HelpCalloutKind.danger: _CalloutStyle(
    PosterColors.error, Color(0x14D9343E), Icons.report_problem_rounded, 'Cannot be undone',
  ),
  HelpCalloutKind.success: _CalloutStyle(
    PosterColors.success, Color(0x1455A868), Icons.check_circle_rounded, 'Good to know',
  ),
  HelpCalloutKind.rule: _CalloutStyle(
    PosterColors.bluePanel, Color(0x14102A58), Icons.lock_rounded, 'Role rule',
  ),
};

class _CalloutView extends StatelessWidget {
  const _CalloutView(this.block);
  final HelpCallout block;

  @override
  Widget build(BuildContext context) {
    final style = _calloutStyles[block.kind]!;
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Container(
        decoration: BoxDecoration(
          color: style.background,
          borderRadius: BorderRadius.circular(8),
          border: Border(left: BorderSide(color: style.color, width: 4)),
        ),
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(style.icon, color: style.color, size: 22),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    (block.title ?? style.defaultTitle).toUpperCase(),
                    style: PosterText.eyebrow.copyWith(color: style.color),
                  ),
                  const SizedBox(height: 4),
                  buildRichText(
                    block.text,
                    PosterText.bodyLarge.copyWith(color: PosterColors.navy, height: 1.4),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TableView extends StatelessWidget {
  const _TableView(this.block);
  final HelpTable block;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        children: [
          for (final row in block.rows) _TableRowCard(headers: block.headers, row: row),
        ],
      ),
    );
  }
}

class _TableRowCard extends StatelessWidget {
  const _TableRowCard({required this.headers, required this.row});
  final List<String> headers;
  final HelpTableRow row;

  @override
  Widget build(BuildContext context) {
    final cells = row.cells;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: PosterColors.white,
        border: Border.all(color: PosterColors.border),
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            cells.first,
            style: PosterText.bodyLarge.copyWith(color: PosterColors.blueDeep, fontWeight: FontWeight.w800),
          ),
          for (var i = 1; i < cells.length; i++) ...[
            const SizedBox(height: 8),
            Text(
              headers[i].toUpperCase(),
              style: PosterText.metadata.copyWith(color: PosterColors.muted),
            ),
            const SizedBox(height: 2),
            Text(
              cells[i],
              style: PosterText.bodyDefault.copyWith(color: PosterColors.navy, height: 1.35),
            ),
          ],
        ],
      ),
    );
  }
}

class _StepFlowView extends StatelessWidget {
  const _StepFlowView(this.block);
  final HelpStepFlow block;

  @override
  Widget build(BuildContext context) {
    final steps = block.steps;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8, top: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (var i = 0; i < steps.length; i++) _StepRow(step: steps[i], index: i, isLast: i == steps.length - 1),
          if (block.terminalNote != null) ...[
            const SizedBox(height: 4),
            _CalloutView(HelpCallout(HelpCalloutKind.warning, block.terminalNote!, title: 'Dead end')),
          ],
        ],
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow({required this.step, required this.index, required this.isLast});
  final HelpStep step;
  final int index;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    const circleSize = 44.0;
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Stack(
                clipBehavior: Clip.none,
                children: [
                  Container(
                    width: circleSize,
                    height: circleSize,
                    decoration: const BoxDecoration(
                      color: PosterColors.navy,
                      shape: BoxShape.circle,
                    ),
                    child: Icon(step.icon, color: PosterColors.goldSoft, size: 22),
                  ),
                  Positioned(
                    right: -2,
                    bottom: -2,
                    child: Container(
                      width: 18,
                      height: 18,
                      alignment: Alignment.center,
                      decoration: const BoxDecoration(color: PosterColors.gold, shape: BoxShape.circle),
                      child: Text(
                        '${index + 1}',
                        style: PosterText.metadata.copyWith(color: PosterColors.navy, fontSize: 10),
                      ),
                    ),
                  ),
                ],
              ),
              if (!isLast) Expanded(child: Container(width: 2, color: PosterColors.border)),
            ],
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 20, top: 4),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: PosterColors.white,
                  border: Border.all(color: PosterColors.border),
                  borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
                  boxShadow: PosterShadows.blue(dx: 3, dy: 3),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      step.title,
                      style: PosterText.cardTitle.copyWith(fontSize: 17, color: PosterColors.navy),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      step.detail,
                      style: PosterText.bodyDefault.copyWith(color: PosterColors.muted, height: 1.35),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

const _roleAccents = <String, Color>{
  'Manager': PosterColors.blue,
  'Owner': PosterColors.gold,
  'Admin': PosterColors.navy,
};

class _RoleListView extends StatelessWidget {
  const _RoleListView(this.block);
  final HelpRoleList block;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        children: [
          for (final role in block.roles) _RoleCard(role: role, accent: _roleAccents[role.role] ?? PosterColors.blue),
        ],
      ),
    );
  }
}

class _RoleCard extends StatelessWidget {
  const _RoleCard({required this.role, required this.accent});
  final HelpRoleInfo role;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: PosterColors.white,
        border: Border.all(color: PosterColors.border),
        borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(color: accent, shape: BoxShape.circle),
            child: Icon(
              role.icon,
              size: 20,
              color: accent == PosterColors.gold ? PosterColors.navy : PosterColors.white,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(role.role, style: PosterText.cardTitle.copyWith(fontSize: 17, color: PosterColors.navy)),
                const SizedBox(height: 3),
                Text(
                  role.description,
                  style: PosterText.bodyDefault.copyWith(color: PosterColors.muted, height: 1.35),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _FaqListView extends StatelessWidget {
  const _FaqListView(this.block);
  final HelpFaqList block;

  @override
  Widget build(BuildContext context) {
    return Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: Column(
        children: [
          for (final entry in block.entries)
            Container(
              margin: const EdgeInsets.only(bottom: 8),
              decoration: BoxDecoration(
                color: PosterColors.white,
                border: Border.all(color: PosterColors.border),
                borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
              ),
              clipBehavior: Clip.antiAlias,
              child: ExpansionTile(
                iconColor: PosterColors.blue,
                collapsedIconColor: PosterColors.muted,
                leading: const Icon(Icons.help_outline_rounded, color: PosterColors.blue),
                title: Text(
                  entry.question,
                  style: PosterText.bodyLarge.copyWith(color: PosterColors.navy, fontWeight: FontWeight.w700),
                ),
                childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                expandedCrossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    entry.answer,
                    style: PosterText.bodyDefault.copyWith(color: PosterColors.muted, height: 1.4),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
