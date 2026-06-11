package com.easyreader.elinkclient

import android.os.Bundle
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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            EasyReaderEinkTheme {
                MainScreen(viewModel = viewModel)
            }
        }
    }

    override fun onStart() {
        super.onStart()
        viewModel.syncOnAppForeground()
    }

    override fun onStop() {
        viewModel.syncOnAppBackground()
        super.onStop()
    }
}
