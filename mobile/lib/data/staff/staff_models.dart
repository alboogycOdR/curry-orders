/// Shared staff-mode models — deliberately kept separate from
/// `data/models.dart` (the customer-facing models file): staff mode
/// (docs/mobile/FLUTTER_APP_PLAN.md Phase 6) was built as several
/// screens in parallel, each in its own file with its own
/// screen-specific models co-located there (see e.g.
/// `features/staff/inbox/inbox_screen.dart`) rather than everyone
/// editing one shared models file at once. Only `StaffUser` — needed by
/// the shared auth state every screen depends on — lives here.
library;

class StaffUser {
  const StaffUser({
    required this.id,
    required this.name,
    required this.email,
    required this.role,
    required this.roleDisplay,
    required this.avatarUrl,
    required this.mustChangePassword,
  });

  factory StaffUser.fromJson(Map<String, dynamic> json) => StaffUser(
        id: json['id'] as int,
        name: json['name'] as String,
        email: json['email'] as String,
        role: json['role'] as String,
        roleDisplay: json['role_display'] as String,
        avatarUrl: (json['avatar_url'] as String?) ?? '',
        mustChangePassword: json['must_change_password'] as bool,
      );

  final int id;
  final String name;
  final String email;
  final String role; // "admin" | "owner" | "manager"
  final String roleDisplay;
  final String avatarUrl;
  final bool mustChangePassword;

  bool get isAdmin => role == 'admin';
  bool get isOwnerOrAdmin => role == 'owner' || role == 'admin';
}
