import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_client.dart';
import '../data/models.dart';
import '../data/repository.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

final apiProvider = Provider<RotiConnectApi>((ref) => RotiConnectApi(ref.watch(apiClientProvider)));

/// `GET /api/v1/days/` — which dates are actually orderable right now
/// (open + before cutoff). Home/Menu/Basket all read the collection date
/// through this rather than assuming "today".
final orderableDaysProvider = FutureProvider<List<OrderableDay>>((ref) {
  return ref.watch(apiProvider).orderableDays();
});

/// `GET /api/v1/featured/` — Home's hero card (added 2026-09-15).
final featuredDishProvider = FutureProvider<FeaturedDish?>((ref) {
  return ref.watch(apiProvider).featuredDish();
});

/// `GET /api/v1/availability/?date=` for one day — Menu/Home read
/// dishes+slots through this rather than calling the repository
/// directly, so every screen sharing a date shares the one in-flight
/// request/cache entry.
final availabilityProvider =
    FutureProvider.family<DayAvailability, String>((ref, isoDate) {
  return ref.watch(apiProvider).availability(isoDate);
});

final orderDetailProvider = FutureProvider.family<OrderDetail, String>((ref, publicToken) {
  return ref.watch(apiProvider).orderStatus(publicToken);
});
