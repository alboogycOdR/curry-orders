/// Thrown by [RotiConnectApi] for every non-2xx response. Mirrors
/// `public/api.py`'s `_error_response` shape — `{"error": code,
/// "message": ..., "fields": {...}?}` — so callers can branch on
/// `code`/`fields` the same way the web JS does on the raw JSON.
class ApiException implements Exception {
  ApiException({
    required this.code,
    required this.message,
    required this.statusCode,
    this.fields,
  });

  final String code;
  final String message;
  final int statusCode;
  final Map<String, String>? fields;

  bool get isAuthRequired => code == 'auth_required';
  bool get isThrottled => code == 'throttled' || code == 'throttled_login';

  @override
  String toString() => 'ApiException($code, $statusCode): $message';
}
