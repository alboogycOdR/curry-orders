/// Design tokens ported from the poster variant style guide:
/// updates0909/handover_poster_variant/Roti Connect Poster Variant - Design
/// & Style Guide.md (§4 colour/shadow, §5.2 type, §6 spacing/radii).
///
/// Do not scatter raw hexes/sizes in widgets — reference these constants,
/// same discipline the guide requires of the web build ("Take every value
/// from a variable").
library;

import 'package:flutter/material.dart';

/// §4.1 colour.
class PosterColors {
  PosterColors._();

  static const navy = Color(0xFF071124);
  static const black = Color(0xFF050A15);
  static const blue = Color(0xFF168CFF);
  static const blueDeep = Color(0xFF0C3679);
  static const bluePanel = Color(0xFF102A58);
  static const gold = Color(0xFFFFC400);
  static const goldSoft = Color(0xFFFFD95A);
  static const white = Color(0xFFFFFFFF);
  static const paper = Color(0xFFF7F8FA);
  static const border = Color(0xFFD3DDEA);
  static const muted = Color(0xFF56647A);
  static const mutedDark = Color(0xFFAEB8C9);
  static const error = Color(0xFFD9343E);
  static const success = Color(0xFF55A868);

  // Shadow offset colours (§4's "hard poster offsets, never soft blurs").
  static const shadowBlueOffset = Color(0xFF0C55B0);
}

/// §4's hard offset shadows — never `BoxShadow` blur, always a flat
/// duplicate panel offset down-right.
class PosterShadows {
  PosterShadows._();

  static List<BoxShadow> gold({double dx = 5, double dy = 6}) => [
        BoxShadow(color: PosterColors.gold, offset: Offset(dx, dy), blurRadius: 0),
      ];

  static List<BoxShadow> blue({double dx = 4, double dy = 4}) => [
        BoxShadow(color: PosterColors.shadowBlueOffset, offset: Offset(dx, dy), blurRadius: 0),
      ];

  static List<BoxShadow> dark({double dx = 6, double dy = 7}) => [
        BoxShadow(color: PosterColors.navy, offset: Offset(dx, dy), blurRadius: 0),
      ];
}

/// §6.1 spacing (4px base) and §6.2 radii.
class PosterSpace {
  PosterSpace._();

  static const unit = 4.0;
  static const pageSidePadding = 18.0;
  static const bottomNavHeight = 72.0;
  static const bottomPagePadding = 96.0; // reserved so content never hides under the tab bar

  static const radiusButton = 5.0; // 4-6px
  static const radiusInput = 4.0; // 3-5px
}

/// §5.2 type scale. All Barlow Condensed unless noted (script accent is a
/// separate family — see [PosterText.scriptAccent] fallback stack in the
/// style guide; not yet bundled, see docs/mobile/FLUTTER_APP_PLAN.md
/// Phase 2 "Barlow Condensed font bundled").
class PosterText {
  PosterText._();

  static const fontFamily = 'BarlowCondensed';

  static const heroDisplay = TextStyle(
    fontFamily: fontFamily,
    fontSize: 72,
    fontWeight: FontWeight.w900,
    height: 0.8,
    shadows: [Shadow(offset: Offset(3, 4), color: Color(0xD90C3679))],
  );

  static const sectionDisplay = TextStyle(
    fontFamily: fontFamily,
    fontSize: 56,
    fontWeight: FontWeight.w900,
    height: 0.82,
  );

  static const drawerTitle = TextStyle(
    fontFamily: fontFamily,
    fontSize: 30,
    fontWeight: FontWeight.w900,
  );

  static const cardTitle = TextStyle(
    fontFamily: fontFamily,
    fontSize: 22,
    fontWeight: FontWeight.w900,
    height: 0.95,
  );

  static const priceHero = TextStyle(
    fontFamily: fontFamily,
    fontSize: 40,
    fontWeight: FontWeight.w900,
  );

  static const priceCard = TextStyle(
    fontFamily: fontFamily,
    fontSize: 26,
    fontWeight: FontWeight.w900,
  );

  static const bodyLarge = TextStyle(fontSize: 15, fontWeight: FontWeight.w500);
  static const bodyDefault = TextStyle(fontSize: 13, fontWeight: FontWeight.w500);

  static const button = TextStyle(
    fontFamily: fontFamily,
    fontSize: 14,
    fontWeight: FontWeight.w900,
    letterSpacing: 0.12 * 14,
  );

  static const eyebrow = TextStyle(
    fontFamily: fontFamily,
    fontSize: 11,
    fontWeight: FontWeight.w900,
    letterSpacing: 0.18 * 11,
  );

  static const metadata = TextStyle(fontSize: 11, fontWeight: FontWeight.w900, letterSpacing: 0.6);
}

/// §4.3 motion (`--ease-poster`).
class PosterMotion {
  PosterMotion._();

  static const ease = Cubic(0.23, 1, 0.32, 1);
  static const buttonPress = Duration(milliseconds: 150);
  static const cardHover = Duration(milliseconds: 210);
  static const drawerSlide = Duration(milliseconds: 340);
  static const modal = Duration(milliseconds: 280);
}
