package com.easyreader.elinkclient.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.material3.Card
import androidx.compose.material3.CardColors
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CardElevation
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.unit.dp

@Composable
fun EinkCard(
    modifier: Modifier = Modifier,
    shape: Shape = CardDefaults.shape,
    colors: CardColors? = null,
    border: BorderStroke? = null,
    elevation: CardElevation = CardDefaults.cardElevation(
        defaultElevation = 0.dp,
        pressedElevation = 0.dp,
        focusedElevation = 0.dp,
        hoveredElevation = 0.dp,
        draggedElevation = 0.dp,
        disabledElevation = 0.dp,
    ),
    content: @Composable ColumnScope.() -> Unit,
) {
    val resolvedColors = colors ?: CardDefaults.cardColors(
        containerColor = MaterialTheme.colorScheme.background,
        contentColor = MaterialTheme.colorScheme.onBackground,
    )
    val resolvedBorder = border ?: BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)

    Card(
        modifier = modifier,
        shape = shape,
        colors = resolvedColors,
        elevation = elevation,
        border = resolvedBorder,
        content = content,
    )
}
