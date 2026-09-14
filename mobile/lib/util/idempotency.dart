import 'dart:math';

/// A random-enough key for the `Idempotency-Key` header
/// `public.api.checkout` requires — no `uuid` package dependency needed
/// for something this small. One key per checkout *attempt* (a new one
/// each time the Place order button is pressed), not per basket — a
/// retry of the same request should reuse the key so the server can
/// detect it as a retry, but a genuinely new order attempt needs a new
/// one.
String generateIdempotencyKey() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  return bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
}
