import 'package:flutter/material.dart';

import '../staff_scaffold.dart';

/// TODO(staff-phase6/menu): replace with the real screen.
/// `dishId == null` -> create; otherwise -> edit (image upload +
/// options/values CRUD live here too, matching `staff/dish_form.html`).
/// Backend: `GET/POST /api/v1/staff/menu/new/`,
/// `GET/POST /api/v1/staff/menu/<id>/`, plus the image/options/archive
/// endpoints listed in `staff/urls_api_mobile.py`
/// (`staff/api_mobile_menu.py`).
/// See docs/mobile/FLUTTER_APP_PLAN.md Phase 6 for the full functional spec.
class DishFormScreen extends StatelessWidget {
  const DishFormScreen({super.key, this.dishId});

  final int? dishId;

  @override
  Widget build(BuildContext context) {
    return StaffScaffold(
      title: dishId == null ? 'New dish' : 'Edit dish',
      body: const Center(child: Text('TODO: Dish form')),
    );
  }
}
