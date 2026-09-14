import 'dart:io';

import 'package:dio/dio.dart';

import 'api_client.dart';
import 'api_exception.dart';
import 'models.dart';

/// One method per `public/api.py` / `public/urls_v1_api.py` endpoint.
/// Every non-2xx response is turned into an [ApiException] here, once —
/// callers (Riverpod notifiers) just try/catch that, they never touch
/// raw status codes.
class RotiConnectApi {
  RotiConnectApi(this._client);

  final ApiClient _client;

  Future<void> primeCsrf() => _client.primeCsrf();

  T _parse<T>(Response<dynamic> response, T Function(dynamic data) parse) {
    final status = response.statusCode ?? 0;
    if (status >= 200 && status < 300) {
      return parse(response.data);
    }
    final data = response.data;
    if (data is Map<String, dynamic>) {
      final rawFields = data['fields'];
      throw ApiException(
        code: (data['error'] as String?) ?? 'unknown',
        message: (data['message'] as String?) ?? 'Something went wrong.',
        statusCode: status,
        fields: rawFields is Map
            ? rawFields.map((key, value) => MapEntry(key.toString(), value.toString()))
            : null,
      );
    }
    throw ApiException(code: 'unknown', message: 'Something went wrong.', statusCode: status);
  }

  Future<List<OrderableDay>> orderableDays() async {
    final resp = await _client.dio.get<dynamic>('days/');
    return _parse(
      resp,
      (d) => ((d as Map<String, dynamic>)['days'] as List<dynamic>)
          .map((day) => OrderableDay.fromJson(day as Map<String, dynamic>))
          .toList(),
    );
  }

  Future<DayAvailability> availability(String isoDate) async {
    final resp = await _client.dio.get<dynamic>('availability/', queryParameters: {'date': isoDate});
    return _parse(resp, (d) => DayAvailability.fromJson(d as Map<String, dynamic>));
  }

  Future<OrderDetail> orderStatus(String publicToken) async {
    final resp = await _client.dio.get<dynamic>('orders/$publicToken/');
    return _parse(resp, (d) => OrderDetail.fromJson(d as Map<String, dynamic>));
  }

  /// Throws `ApiException(code: 'illegal_transition')` for an order
  /// that isn't `collected` yet — callers should only offer this action
  /// when `OrderDetail.canReorder` is already true.
  Future<ReorderResult> reorder(String publicToken) async {
    final resp = await _client.dio.get<dynamic>('orders/$publicToken/reorder/');
    return _parse(resp, (d) => ReorderResult.fromJson(d as Map<String, dynamic>));
  }

  /// `order_number` blank + `mobile` set requires a signed-in session
  /// (see `public.api.lookup_json`'s own docstring) — throws
  /// `ApiException(code: 'auth_required')` otherwise.
  Future<List<OrderDetail>> lookup({String orderNumber = '', required String mobile}) async {
    final resp = await _client.dio.post<dynamic>(
      'lookup/',
      data: {'order_number': orderNumber, 'mobile': mobile},
    );
    return _parse(
      resp,
      (d) => ((d as Map<String, dynamic>)['orders'] as List<dynamic>)
          .map((o) => OrderDetail.fromJson(o as Map<String, dynamic>))
          .toList(),
    );
  }

  Future<CustomerAccount> login({required String mobile, required String password}) async {
    final resp = await _client.dio.post<dynamic>(
      'auth/login/',
      data: {'mobile': mobile, 'password': password},
    );
    return _parse(resp, (d) => CustomerAccount.fromJson(d as Map<String, dynamic>));
  }

  Future<CustomerAccount> signup({
    required String name,
    required String mobile,
    required String password,
  }) async {
    final resp = await _client.dio.post<dynamic>(
      'auth/signup/',
      data: {'name': name, 'mobile': mobile, 'password': password},
    );
    return _parse(resp, (d) => CustomerAccount.fromJson(d as Map<String, dynamic>));
  }

  Future<void> logout() async {
    final resp = await _client.dio.post<dynamic>('auth/logout/');
    _parse(resp, (_) => null);
  }

  /// Throws `ApiException(code: 'auth_required')` when signed out —
  /// callers should treat that as "show the sign-in screen", not a
  /// generic error banner.
  Future<CustomerAccount> account() async {
    final resp = await _client.dio.get<dynamic>('account/');
    return _parse(resp, (d) => CustomerAccount.fromJson(d as Map<String, dynamic>));
  }

  Future<List<OrderSummary>> accountOrders() async {
    final resp = await _client.dio.get<dynamic>('account/orders/');
    return _parse(
      resp,
      (d) => ((d as Map<String, dynamic>)['orders'] as List<dynamic>)
          .map((o) => OrderSummary.fromJson(o as Map<String, dynamic>))
          .toList(),
    );
  }

  /// `payload` matches `public.api._validate_payload`'s field table
  /// (name/mobile/note/date/slot_id/payment_method/collection_method/
  /// accept_policies/lines) — built by the basket/checkout screen, not
  /// this layer, since only the UI knows the current cart contents.
  Future<Map<String, dynamic>> checkout(
    Map<String, dynamic> payload, {
    required String idempotencyKey,
  }) async {
    final resp = await _client.dio.post<dynamic>(
      'checkout/',
      data: payload,
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return _parse(resp, (d) => d as Map<String, dynamic>);
  }

  /// `POST /api/v1/orders/:token/proof/` — multipart, one `file` field.
  /// See `public.api.upload_proof`'s docstring for the validation order
  /// (400 `upload_invalid` before any throttle spend, then 409
  /// `illegal_transition` if the order moved past `awaiting_eft`/
  /// `payment_review` since the page loaded, 429 `throttled`).
  Future<String> uploadProof(String publicToken, {required File file}) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(file.path),
    });
    final resp = await _client.dio.post<dynamic>('orders/$publicToken/proof/', data: formData);
    return _parse(resp, (d) => (d as Map<String, dynamic>)['status'] as String);
  }
}
