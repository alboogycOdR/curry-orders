import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import 'app/router.dart';
import 'data/api_client.dart';
import 'state/api_providers.dart';
import 'state/notifications.dart';
import 'theme/poster_theme.dart';

/// Handles a push notification that arrives while the app is fully
/// backgrounded/terminated (mobile Phase 8). Must be a top-level (or
/// static) function, not a closure — the Android side runs it in its
/// own isolate, separate from the one `main()` runs in, so it can't
/// close over anything from app state. There's nothing to do here
/// beyond letting the OS show the notification (the default behaviour
/// for a message with a `notification` payload, which every send from
/// `core.notifications` always includes) — no local data to update,
/// no navigation possible from a background isolate.
@pragma('vm:entry-point')
Future<void> _firebaseBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // google-services.json (mobile/android/app/) makes this resolve;
  // without it this throws, which is exactly why nothing under
  // features/staff/notifications/ called Firebase.* before that file
  // existed (docs/mobile/FLUTTER_APP_PLAN.md Phase 8's own note on
  // this).
  await Firebase.initializeApp();
  FirebaseMessaging.onBackgroundMessage(_firebaseBackgroundHandler);

  // Resolved once, here, before runApp() -- getApplicationDocumentsDirectory
  // is inherently async (a real platform-channel call), and ApiClient's own
  // constructor deliberately stays synchronous rather than pushing that
  // await onto every `ref.watch(apiClientProvider)` call site (see that
  // class's own docstring). This is what makes the session survive an app
  // restart at all -- the prerequisite fingerprint sign-in (Phase 9,
  // state/biometric_auth.dart) actually gates.
  final cookieDir = await getApplicationDocumentsDirectory();
  final apiClient = ApiClient(cookieStorageDir: '${cookieDir.path}/.cookies');

  runApp(
    ProviderScope(
      overrides: [apiClientProvider.overrideWithValue(apiClient)],
      child: const RotiConnectApp(),
    ),
  );
}

class RotiConnectApp extends ConsumerStatefulWidget {
  const RotiConnectApp({super.key});

  @override
  ConsumerState<RotiConnectApp> createState() => _RotiConnectAppState();
}

class _RotiConnectAppState extends ConsumerState<RotiConnectApp> {
  @override
  void initState() {
    super.initState();
    // Fire-and-forget: primes the csrftoken cookie before the user can
    // possibly reach a POST screen. A POST issued before this resolves
    // would still work (api_client.dart re-reads the cookie jar fresh
    // on every request) as long as this beats the user to the first tap.
    ref.read(apiClientProvider).primeCsrf();
    // Also fire-and-forget: if notifications were already turned on in
    // a previous session (state/notifications.dart's own persisted
    // preference), re-request permission/register this launch's token
    // without the user having to revisit the Notifications screen.
    // A fresh install / first-ever launch starts with the preference
    // off, so this is a no-op until they opt in once.
    ref.read(notificationsEnabledProvider.notifier).reapplyIfEnabled();
    listenForForegroundMessages();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Roti Connect Staff',
      debugShowCheckedModeBanner: false,
      theme: PosterTheme.light,
      routerConfig: appRouter,
      scaffoldMessengerKey: rootScaffoldMessengerKey,
      // The system/gesture back button always returns to Inbox first,
      // from anywhere in the app — a bottom-nav tab, or any screen
      // pushed from the More list (Cash, Menu editor, Team, ...), no
      // matter how many levels deep. Explicit direction: this is a
      // staff kitchen tool, not a document-style app with a "natural"
      // back history worth preserving — one predictable "take me home"
      // button beats retracing whatever path got them here. Pressing
      // back again once already on Inbox falls through to the normal
      // "exit the app" behaviour, not a second no-op.
      //
      // `canPop: false` here means *every* system pop is intercepted
      // app-wide (this wraps the whole routed `child`, not one
      // screen) — `onPopInvokedWithResult` is where the actual
      // decision happens, reading the router's own current location
      // directly (`appRouter.routerDelegate.currentConfiguration`)
      // rather than `GoRouterState.of(context)`, since this `builder`
      // sits above the Router in the widget tree and wouldn't reliably
      // resolve the latter.
      builder: (context, child) => PopScope(
        canPop: false,
        onPopInvokedWithResult: (didPop, result) {
          if (didPop) return;
          final location = appRouter.routerDelegate.currentConfiguration.uri.toString();
          if (location == '/staff/inbox') {
            SystemNavigator.pop();
          } else {
            appRouter.go('/staff/inbox');
          }
        },
        child: child!,
      ),
    );
  }
}
