package com.easyreader.elinkclient

import android.os.Bundle
import android.os.SystemClock
import android.view.KeyEvent
import androidx.activity.OnBackPressedCallback
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import com.easyreader.elinkclient.ui.EinkViewModel
import com.easyreader.elinkclient.ui.MainScreen
import com.easyreader.elinkclient.ui.theme.EasyReaderEinkTheme

class MainActivity : ComponentActivity() {
    private val viewModel: EinkViewModel by viewModels {
        EinkViewModel.factory(application)
    }
    private val launchStartElapsedMs = SystemClock.elapsedRealtime()
    private var hasStartedOnce = false
    private var exitSyncInProgress = false
    private var firstScreenReported = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val resolvedViewModel = viewModel
        setContent {
            EasyReaderEinkTheme {
                MainScreen(viewModel = resolvedViewModel)
            }
        }

        val exitBackCallback = object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (exitSyncInProgress) {
                    return
                }
                exitSyncInProgress = true
                val callback = this
                viewModel.syncBeforeExit {
                    exitSyncInProgress = false
                    callback.isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        }
        onBackPressedDispatcher.addCallback(this, exitBackCallback)
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus && !firstScreenReported) {
            firstScreenReported = true
            val elapsedMs = SystemClock.elapsedRealtime() - launchStartElapsedMs
            viewModel.onFirstScreenDisplayed(elapsedMs)
        }
    }

    override fun onStart() {
        super.onStart()
        if (!hasStartedOnce) {
            hasStartedOnce = true
            return
        }
        viewModel.syncOnAppForeground()
    }

    override fun onStop() {
        viewModel.syncOnAppBackground(allowNetworkSync = !isFinishing)
        super.onStop()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (viewModel.handleReaderHardwareKey(keyCode)) {
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

}
