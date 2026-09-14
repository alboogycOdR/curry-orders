import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The collection date the customer is currently browsing/ordering for.
/// `null` means "not chosen yet" — Menu/Basket fall back to the soonest
/// orderable day (`orderableDaysProvider`'s first entry) until the
/// customer picks a different one.
final selectedDayIsoProvider = StateProvider<String?>((ref) => null);

/// Menu's category filter chip — `'all'` shows everything.
final selectedCategoryProvider = StateProvider<String>((ref) => 'all');
