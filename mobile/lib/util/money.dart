/// Dart port of `core.money.format_cents` — `"R 185.00"` / `"R 1 000.00"`,
/// space-separated thousands, always two decimals (spec §11.1). Keep in
/// sync with that function if it ever changes.
String formatCents(int cents) {
  final sign = cents < 0 ? '-' : '';
  final absCents = cents.abs();
  final wholeRand = absCents ~/ 100;
  final subCents = absCents % 100;
  final grouped = _groupThousands(wholeRand);
  return '${sign}R $grouped.${subCents.toString().padLeft(2, '0')}';
}

String _groupThousands(int value) {
  final digits = value.toString();
  final buffer = StringBuffer();
  for (var i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 == 0) buffer.write(' ');
    buffer.write(digits[i]);
  }
  return buffer.toString();
}
