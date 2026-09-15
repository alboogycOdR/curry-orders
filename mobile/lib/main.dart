import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/router.dart';
import 'state/api_providers.dart';
import 'theme/poster_theme.dart';

void main() {
  runApp(const ProviderScope(child: RotiConnectApp()));
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
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Roti Connect Staff',
      debugShowCheckedModeBanner: false,
      theme: PosterTheme.light,
      routerConfig: appRouter,
    );
  }
}
