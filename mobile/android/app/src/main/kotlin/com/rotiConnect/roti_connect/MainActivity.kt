package com.rotiConnect.roti_connect

import android.content.Intent
import android.net.Uri
import android.os.PowerManager
import android.provider.Settings
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/// `FlutterFragmentActivity`, not the default `FlutterActivity` the
/// Flutter template generates — required by `local_auth` (fingerprint
/// sign-in, mobile Phase 9): its Android implementation shows a real
/// `BiometricPrompt`, which needs a `FragmentActivity` host to attach
/// to. Also hosts a small hand-written platform channel for battery-
/// optimisation exemption (same phase) — not exposed by
/// `firebase_messaging`/any other plugin already in this app, so a
/// couple of one-line `PowerManager`/`Settings` calls here is simpler
/// and safer than adding a whole extra package for it. See
/// `lib/state/battery_optimization.dart` for the Dart side and why
/// this matters specifically for this app: several Android OEM battery
/// managers (not stock Android's own Doze mode, which Firebase already
/// handles correctly) kill backgrounded apps aggressively enough to
/// silently stop FCM delivery — this lets a kitchen device be
/// explicitly exempted.
class MainActivity : FlutterFragmentActivity() {
    private val channel = "roti_connect/battery_optimization"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channel).setMethodCallHandler { call, result ->
            when (call.method) {
                "isIgnoringBatteryOptimizations" -> {
                    val powerManager = getSystemService(POWER_SERVICE) as PowerManager
                    result.success(powerManager.isIgnoringBatteryOptimizations(packageName))
                }
                "requestIgnoreBatteryOptimizations" -> {
                    // The system's own "allow this app to ignore battery
                    // optimisations?" dialog — the user still has to
                    // confirm it there; this only opens it. A no-op
                    // (Android just closes it immediately) if already
                    // exempted, so it's safe to call unconditionally.
                    val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                        data = Uri.parse("package:$packageName")
                    }
                    startActivity(intent)
                    result.success(null)
                }
                "openBatteryOptimizationSettings" -> {
                    // Fallback for the rare device where the direct-request
                    // intent above isn't supported (some OEM skins) — opens
                    // the general "ignore optimisations" list instead, same
                    // destination a user would reach manually.
                    val intent = Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)
                    startActivity(intent)
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
    }
}
