import 'package:flutter/material.dart';

import 'poster_tokens.dart';

/// `ThemeData` built from [PosterColors]/[PosterText] — the single place
/// that turns design tokens into a Flutter theme. Screens should read
/// styles off `Theme.of(context)` / these constants, not hardcode values.
class PosterTheme {
  PosterTheme._();

  static ThemeData get light {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: PosterColors.paper,
      colorScheme: const ColorScheme.light(
        primary: PosterColors.blue,
        secondary: PosterColors.gold,
        surface: PosterColors.white,
        error: PosterColors.error,
      ),
      fontFamily: PosterText.fontFamily,
    );

    return base.copyWith(
      appBarTheme: const AppBarTheme(
        backgroundColor: PosterColors.navy,
        foregroundColor: PosterColors.white,
        elevation: 0,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: PosterColors.gold,
          foregroundColor: PosterColors.navy,
          textStyle: PosterText.button,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(PosterSpace.radiusButton),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: PosterColors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(PosterSpace.radiusInput),
          borderSide: const BorderSide(color: PosterColors.border),
        ),
      ),
    );
  }
}
