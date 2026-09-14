import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';

/// Points at the poster-variant deploy per docs/DEPLOYMENTS.md — dev/test
/// only, no build-flavor split yet. Swap for a real HTTPS domain once
/// Caddy/TLS lands (docs/DOMAIN_AND_SSL.md) — and delete
/// `android/app/src/main/res/xml/network_security_config.xml`'s
/// cleartext carve-out for this IP at the same time. See
/// docs/mobile/FLUTTER_APP_PLAN.md Phase 2/5.
const _devBaseUrl = 'http://204.168.249.99:8105/api/v1/';

/// Thin wrapper around [Dio] that carries the Django session across
/// requests (a cookie jar — dio has none built in) and attaches
/// `X-CSRFToken` on every mutating request, mirroring the web JS's
/// `getCookie('csrftoken')` dance. See `public.api.csrf_cookie`'s own
/// docstring for the server side of this.
///
/// The cookie jar is in-memory only — a fresh app launch means a fresh
/// session (the user has to sign in again). Persisting it across
/// restarts (`PersistCookieJar` + `path_provider`) is a reasonable Phase
/// 4 addition once the rest of the auth flow is proven out.
class ApiClient {
  ApiClient({String baseUrl = _devBaseUrl}) : dio = Dio(
          BaseOptions(
            baseUrl: baseUrl,
            connectTimeout: const Duration(seconds: 10),
            receiveTimeout: const Duration(seconds: 15),
            // Handle 4xx/5xx bodies ourselves (public/api.py always
            // returns a JSON {error, message} body, even on failure) —
            // letting dio throw would discard that body.
            validateStatus: (_) => true,
          ),
        ) {
    dio.interceptors.add(CookieManager(cookieJar));
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          if (_needsCsrf(options.method)) {
            final token = await _csrfToken(dio.options.baseUrl);
            if (token != null) options.headers['X-CSRFToken'] = token;
          }
          handler.next(options);
        },
      ),
    );
  }

  final Dio dio;
  final CookieJar cookieJar = CookieJar();

  static bool _needsCsrf(String method) =>
      const {'POST', 'PUT', 'PATCH', 'DELETE'}.contains(method.toUpperCase());

  Future<String?> _csrfToken(String baseUrl) async {
    final cookies = await cookieJar.loadForRequest(Uri.parse(baseUrl));
    for (final cookie in cookies) {
      if (cookie.name == 'csrftoken') return cookie.value;
    }
    return null;
  }

  /// Call once at app start (`ProviderScope` init or splash) so the
  /// first real POST already has a `csrftoken` cookie to send back.
  Future<void> primeCsrf() => dio.get<void>('csrf/');
}
