package com.easyreader.elinkclient.ui.theme

import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LocalRippleConfiguration
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Composable

private val EinkLightColorScheme = lightColorScheme(
    primary = InkBlack,
    onPrimary = InkWhite,
    secondary = InkGray,
    onSecondary = InkWhite,
    background = InkWhite,
    onBackground = InkBlack,
    surface = InkLightGray,
    onSurface = InkBlack,
)

private val EinkDarkColorScheme = darkColorScheme(
    primary = InkWhite,
    onPrimary = InkBlack,
    secondary = InkLightGray,
    onSecondary = InkBlack,
    background = InkBlack,
    onBackground = InkWhite,
    surface = InkGray,
    onSurface = InkWhite,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EasyReaderEinkTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = EinkLightColorScheme,
        typography = MaterialTheme.typography,
    ) {
        CompositionLocalProvider(
            LocalRippleConfiguration provides null,
            content = content,
        )
    }
}
