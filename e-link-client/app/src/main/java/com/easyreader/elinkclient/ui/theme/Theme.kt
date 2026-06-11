package com.easyreader.elinkclient.ui.theme

import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LocalAbsoluteTonalElevation
import androidx.compose.material3.LocalRippleConfiguration
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Composable
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

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

private val EinkTypography = Typography(
    displayLarge = TextStyle(fontSize = 36.sp, lineHeight = 44.sp, fontWeight = FontWeight.Bold),
    displayMedium = TextStyle(fontSize = 32.sp, lineHeight = 40.sp, fontWeight = FontWeight.Bold),
    displaySmall = TextStyle(fontSize = 28.sp, lineHeight = 36.sp, fontWeight = FontWeight.SemiBold),
    headlineLarge = TextStyle(fontSize = 28.sp, lineHeight = 36.sp, fontWeight = FontWeight.SemiBold),
    headlineMedium = TextStyle(fontSize = 24.sp, lineHeight = 32.sp, fontWeight = FontWeight.SemiBold),
    headlineSmall = TextStyle(fontSize = 22.sp, lineHeight = 30.sp, fontWeight = FontWeight.SemiBold),
    titleLarge = TextStyle(fontSize = 24.sp, lineHeight = 32.sp, fontWeight = FontWeight.SemiBold),
    titleMedium = TextStyle(fontSize = 22.sp, lineHeight = 30.sp, fontWeight = FontWeight.Medium),
    titleSmall = TextStyle(fontSize = 20.sp, lineHeight = 28.sp, fontWeight = FontWeight.Medium),
    bodyLarge = TextStyle(fontSize = 20.sp, lineHeight = 28.sp),
    bodyMedium = TextStyle(fontSize = 20.sp, lineHeight = 28.sp),
    bodySmall = TextStyle(fontSize = 20.sp, lineHeight = 28.sp),
    labelLarge = TextStyle(fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.Medium),
    labelMedium = TextStyle(fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.Medium),
    labelSmall = TextStyle(fontSize = 20.sp, lineHeight = 26.sp),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EasyReaderEinkTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = EinkLightColorScheme,
        typography = EinkTypography,
    ) {
        CompositionLocalProvider(
            LocalRippleConfiguration provides null,
            LocalAbsoluteTonalElevation provides 0.dp,
            content = content,
        )
    }
}
