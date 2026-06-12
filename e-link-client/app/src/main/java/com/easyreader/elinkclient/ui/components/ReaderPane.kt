package com.easyreader.elinkclient.ui.components

import android.graphics.Color as AndroidColor
import android.graphics.Typeface
import android.view.ViewGroup
import android.widget.ScrollView
import android.widget.TextView
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.easyreader.elinkclient.core.EinkDeviceRefreshBridge
import com.easyreader.elinkclient.core.RefreshAction
import com.easyreader.elinkclient.ui.AutoPageTurnSpeedConfig
import com.easyreader.elinkclient.ui.EinkUiState
import com.easyreader.elinkclient.ui.ReaderHardwareAction
import com.easyreader.elinkclient.ui.ReaderFontStyle
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.delay
import kotlin.math.roundToInt

@Composable
fun ReaderPane(
    state: EinkUiState,
    onOpenChapter: (Int) -> Unit,
    onPrevChapter: () -> Unit,
    onNextChapter: () -> Unit,
    onUpdateChapterPosition: (Double) -> Unit,
    onToggleAutoTurn: () -> Unit,
    onIncreaseAutoTurnSpeed: () -> Unit,
    onDecreaseAutoTurnSpeed: () -> Unit,
    onCycleReaderFont: () -> Unit,
    onIncreaseFontSize: () -> Unit,
    onDecreaseFontSize: () -> Unit,
    onIncreaseLineSpacing: () -> Unit,
    onDecreaseLineSpacing: () -> Unit,
    onRequestCacheCurrentBook: () -> Unit,
    onExitReader: () -> Unit,
) {
    if (state.activeBookKey.isNullOrBlank()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(12.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = "当前没有打开书籍，请先从书架进入阅读。",
                style = MaterialTheme.typography.titleMedium,
            )
            OutlinedButton(
                onClick = onExitReader,
                modifier = Modifier.padding(top = 10.dp),
            ) {
                Text("返回")
            }
        }
        return
    }

    val hostView = LocalView.current
    val latestPositionCallback by rememberUpdatedState(onUpdateChapterPosition)
    var showQuickMenu by remember { mutableStateOf(false) }
    var showToc by remember { mutableStateOf(false) }
    var readerScrollView by remember { mutableStateOf<ScrollView?>(null) }
    val noRippleSource = remember { MutableInteractionSource() }
    val chapterRenderKey = listOf(
        state.activeBookKey.orEmpty(),
        state.activeSourceUrl.orEmpty(),
        state.activeChapterListIndex.toString(),
    ).joinToString("|")
    val chapterRestoreKey = "$chapterRenderKey|${state.chapterRestoreToken}"
    var inChapterTurnCount by remember(chapterRenderKey, state.refreshEveryTurns) {
        mutableStateOf(0)
    }

    var previousKeepScreenOn by remember(hostView) { mutableStateOf(hostView.keepScreenOn) }

    DisposableEffect(hostView, state.autoPageTurnEnabled) {
        if (state.autoPageTurnEnabled) {
            previousKeepScreenOn = hostView.keepScreenOn
            hostView.keepScreenOn = true
        } else {
            hostView.keepScreenOn = previousKeepScreenOn
        }

        onDispose {
            hostView.keepScreenOn = previousKeepScreenOn
        }
    }

    LaunchedEffect(state.refreshSignal) {
        if (state.lastRefreshAction != RefreshAction.NONE) {
            EinkDeviceRefreshBridge.apply(hostView, state.lastRefreshAction)
        }
    }

    val chapterIndicator = "第 ${state.activeChapterListIndex + 1}/${state.chapters.size.coerceAtLeast(1)} 章"
    val readingProgressLabel = if (state.chapterType == "novel") {
        "$chapterIndicator · ${(state.activeChapterPosition * 100).roundToInt()}%"
    } else {
        chapterIndicator
    }
    val fontLabel = state.readerFonts.firstOrNull { it.key == state.readerFontKey }?.name
        ?: if (state.readerFontStyle == ReaderFontStyle.SERIF) "衬线" else "无衬线"
    val customTypeface = remember(state.readerFontPath) {
        val fontPath = state.readerFontPath
        if (fontPath.isNullOrBlank()) {
            null
        } else {
            runCatching {
                val file = File(fontPath)
                if (file.exists()) Typeface.createFromFile(file) else null
            }.getOrNull()
        }
    }
    val readerTextColor = MaterialTheme.colorScheme.onBackground.toArgb()
    val clockFormatter = remember { SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.CHINA) }
    var currentDateTimeLabel by remember { mutableStateOf(clockFormatter.format(Date())) }
    val chapterTitleLabel = if (state.activeChapterTitle.isBlank()) {
        chapterIndicator
    } else {
        "$chapterIndicator · ${state.activeChapterTitle}"
    }

    LaunchedEffect(Unit) {
        while (true) {
            currentDateTimeLabel = clockFormatter.format(Date())
            delay(60_000L)
        }
    }

    fun calculateReadingPosition(scrollView: ScrollView, textView: TextView): Double {
        val viewportHeight = (scrollView.height - scrollView.paddingTop - scrollView.paddingBottom).coerceAtLeast(0)
        val contentHeight = textView.height.coerceAtLeast(0)
        val maxScroll = (contentHeight - viewportHeight).coerceAtLeast(0)
        if (maxScroll <= 0) {
            return 0.0
        }
        return (scrollView.scrollY.coerceAtLeast(0).toDouble() / maxScroll.toDouble()).coerceIn(0.0, 1.0)
    }

    fun applyInChapterRefresh() {
        inChapterTurnCount += 1
        val refreshAction = if (inChapterTurnCount % state.refreshEveryTurns.coerceAtLeast(1) == 0) {
            RefreshAction.FULL
        } else {
            RefreshAction.PARTIAL
        }
        EinkDeviceRefreshBridge.apply(hostView, refreshAction)
    }

    fun turnPage(forward: Boolean) {
        if (state.isLoading) {
            return
        }
        val scrollView = readerScrollView ?: return
        val textView = scrollView.getChildAt(0) as? TextView ?: return
        val viewportHeight = (scrollView.height - scrollView.paddingTop - scrollView.paddingBottom).coerceAtLeast(0)
        val contentHeight = textView.height.coerceAtLeast(0)
        if (viewportHeight == 0 || contentHeight == 0) {
            return
        }

        val maxScroll = (contentHeight - viewportHeight).coerceAtLeast(0)
        val currentScroll = scrollView.scrollY.coerceAtLeast(0)

        if (forward) {
            if (!scrollView.canScrollVertically(1) || currentScroll >= maxScroll) {
                onNextChapter()
                return
            }
            val targetScroll = (currentScroll + viewportHeight).coerceAtMost(maxScroll)
            if (targetScroll == currentScroll) {
                onNextChapter()
                return
            }
            scrollView.scrollTo(0, targetScroll)
            applyInChapterRefresh()
            latestPositionCallback(calculateReadingPosition(scrollView, textView))
            return
        }

        if (!scrollView.canScrollVertically(-1) || currentScroll <= 0) {
            onPrevChapter()
            return
        }
        val targetScroll = (currentScroll - viewportHeight).coerceAtLeast(0)
        if (targetScroll == currentScroll) {
            onPrevChapter()
            return
        }
        scrollView.scrollTo(0, targetScroll)
        applyInChapterRefresh()
        latestPositionCallback(calculateReadingPosition(scrollView, textView))
    }

    fun openQuickMenuFromTouch() {
        showQuickMenu = true
    }

    LaunchedEffect(
        state.autoPageTurnEnabled,
        state.autoPageTurnIntervalMs,
        state.chapterType,
        state.activeChapterCached,
        state.activeChapterListIndex,
        state.chapterText,
        state.isLoading,
    ) {
        if (
            !state.autoPageTurnEnabled ||
            state.chapterType != "novel" ||
            !state.activeChapterCached ||
            state.isLoading
        ) {
            return@LaunchedEffect
        }

        while (state.autoPageTurnEnabled) {
            delay(state.autoPageTurnIntervalMs)
            if (!state.autoPageTurnEnabled) {
                break
            }
            turnPage(forward = true)
        }
    }

    LaunchedEffect(state.readerCommandSignal) {
        when (state.pendingReaderCommand) {
            ReaderHardwareAction.PREVIOUS_PAGE -> turnPage(forward = false)
            ReaderHardwareAction.NEXT_PAGE -> turnPage(forward = true)
            ReaderHardwareAction.NONE -> Unit
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.White)
            .padding(horizontal = 10.dp, vertical = 6.dp),
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 2.dp, vertical = 2.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = state.activeBookName.ifBlank { "EasyReader" },
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    text = currentDateTimeLabel,
                    style = MaterialTheme.typography.labelSmall,
                    modifier = Modifier.padding(start = 8.dp),
                )
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .padding(vertical = 4.dp),
            ) {
                if (!state.activeChapterCached) {
                    EinkCard(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(vertical = 8.dp),
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(12.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp, Alignment.CenterVertically),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text(
                                text = state.chapterText,
                                style = MaterialTheme.typography.bodyMedium,
                            )
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                OutlinedButton(
                                    onClick = { showToc = true },
                                    modifier = Modifier.weight(1f),
                                ) {
                                    Text("目录")
                                }
                                EinkButton(
                                    onClick = {
                                        onRequestCacheCurrentBook()
                                    },
                                    modifier = Modifier.weight(1f),
                                ) {
                                    Text("更新本地缓存")
                                }
                            }
                        }
                    }
                } else {
                    AndroidView(
                        modifier = Modifier.fillMaxSize(),
                        factory = { context ->
                            ScrollView(context).apply {
                                readerScrollView = this
                                isFillViewport = true
                                overScrollMode = ScrollView.OVER_SCROLL_NEVER
                                setBackgroundColor(AndroidColor.WHITE)
                                addView(
                                    TextView(context).apply {
                                        includeFontPadding = false
                                        setPadding(0, 4, 0, 16)
                                        setTextColor(readerTextColor)
                                        setBackgroundColor(AndroidColor.WHITE)
                                    },
                                    ViewGroup.LayoutParams(
                                        ViewGroup.LayoutParams.MATCH_PARENT,
                                        ViewGroup.LayoutParams.WRAP_CONTENT,
                                    ),
                                )
                            }
                        },
                        update = { scrollView ->
                            readerScrollView = scrollView
                            val textView = scrollView.getChildAt(0) as TextView
                            scrollView.setBackgroundColor(AndroidColor.WHITE)
                            scrollView.setOnScrollChangeListener { view, _, _, _, _ ->
                                if (state.chapterType == "novel" && state.activeChapterCached) {
                                    val scrollingView = view as? ScrollView ?: return@setOnScrollChangeListener
                                    val contentView = scrollingView.getChildAt(0) as? TextView ?: return@setOnScrollChangeListener
                                    latestPositionCallback(calculateReadingPosition(scrollingView, contentView))
                                }
                            }
                            textView.text = state.chapterText
                            textView.setBackgroundColor(AndroidColor.WHITE)
                            textView.setTextColor(readerTextColor)
                            textView.textSize = state.readerFontSizeSp.toFloat()
                            textView.setLineSpacing(0f, state.readerLineSpacing)
                            textView.typeface = customTypeface ?: when (state.readerFontStyle) {
                                ReaderFontStyle.SANS -> Typeface.SANS_SERIF
                                ReaderFontStyle.SERIF -> Typeface.SERIF
                            }
                            val previousChapterKey = scrollView.tag as? String
                            if (previousChapterKey != chapterRestoreKey) {
                                scrollView.tag = chapterRestoreKey
                                scrollView.post {
                                    val viewportHeight = (scrollView.height - scrollView.paddingTop - scrollView.paddingBottom).coerceAtLeast(0)
                                    val contentHeight = textView.height.coerceAtLeast(0)
                                    val maxScroll = (contentHeight - viewportHeight).coerceAtLeast(0)
                                    val targetScroll = (maxScroll * state.activeChapterPosition).roundToInt().coerceIn(0, maxScroll)
                                    scrollView.scrollTo(0, targetScroll)
                                    latestPositionCallback(calculateReadingPosition(scrollView, textView))
                                }
                            }
                        },
                    )

                    Row(modifier = Modifier.fillMaxSize()) {
                        Column(modifier = Modifier.fillMaxSize()) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .weight(2f)
                                    .clickable(
                                        interactionSource = noRippleSource,
                                        indication = null,
                                        onClick = { openQuickMenuFromTouch() },
                                    ),
                            )

                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .weight(3f),
                            ) {
                                Box(
                                    modifier = Modifier
                                        .weight(2f)
                                        .fillMaxHeight()
                                        .clickable(
                                            interactionSource = noRippleSource,
                                            indication = null,
                                            onClick = { turnPage(forward = false) },
                                        ),
                                )
                                Box(
                                    modifier = Modifier
                                        .weight(3f)
                                        .fillMaxHeight()
                                        .clickable(
                                            interactionSource = noRippleSource,
                                            indication = null,
                                            onClick = { turnPage(forward = true) },
                                        ),
                                )
                            }
                        }
                    }
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedButton(
                    onClick = onToggleAutoTurn,
                    modifier = Modifier.weight(1f),
                ) {
                    Text(
                        if (state.autoPageTurnEnabled) {
                            "自动翻页中"
                        } else {
                            "自动翻页"
                        }
                    )
                }
                Text(
                    text = chapterTitleLabel,
                    style = MaterialTheme.typography.bodySmall,
                    textAlign = TextAlign.Center,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(2f),
                )
                OutlinedButton(
                    onClick = onExitReader,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("退出阅读")
                }
            }
        }

        if (showQuickMenu) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clickable(
                        interactionSource = noRippleSource,
                        indication = null,
                        onClick = { showQuickMenu = false },
                    ),
            )

            EinkCard(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .fillMaxWidth()
                    .padding(top = 38.dp),
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(10.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        text = state.activeBookName.ifBlank { "EasyReader" },
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Text(
                        text = readingProgressLabel,
                        style = MaterialTheme.typography.bodySmall,
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedButton(
                            onClick = {
                                showQuickMenu = false
                                showToc = true
                            },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("目录")
                        }
                        OutlinedButton(
                            onClick = onExitReader,
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("退出阅读")
                        }
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedButton(
                            onClick = {
                                onCycleReaderFont()
                                showQuickMenu = false
                            },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("字体: $fontLabel")
                        }
                        OutlinedButton(
                            onClick = {
                                onToggleAutoTurn()
                            },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text(
                                if (state.autoPageTurnEnabled) {
                                    "自动翻页: 开"
                                } else {
                                    "自动翻页: 关"
                                }
                            )
                        }
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        OutlinedButton(
                            onClick = {
                                onDecreaseAutoTurnSpeed()
                            },
                            enabled = state.autoPageTurnIntervalMs < AutoPageTurnSpeedConfig.MAX_INTERVAL_MS,
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("减速")
                        }
                        Text(
                            text = AutoPageTurnSpeedConfig.formatLabel(state.autoPageTurnIntervalMs),
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.weight(1f),
                        )
                        OutlinedButton(
                            onClick = {
                                onIncreaseAutoTurnSpeed()
                            },
                            enabled = state.autoPageTurnIntervalMs > AutoPageTurnSpeedConfig.MIN_INTERVAL_MS,
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("加速")
                        }
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        OutlinedButton(
                            onClick = {
                                onDecreaseFontSize()
                                showQuickMenu = false
                            },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("字号-")
                        }
                        Text(
                            text = "字号 ${state.readerFontSizeSp}",
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.weight(1f),
                        )
                        OutlinedButton(
                            onClick = {
                                onIncreaseFontSize()
                                showQuickMenu = false
                            },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("字号+")
                        }
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        OutlinedButton(
                            onClick = {
                                onDecreaseLineSpacing()
                                showQuickMenu = false
                            },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("间距-")
                        }
                        Text(
                            text = "间距 ${"%.2f".format(state.readerLineSpacing)}",
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.weight(1f),
                        )
                        OutlinedButton(
                            onClick = {
                                onIncreaseLineSpacing()
                                showQuickMenu = false
                            },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("间距+")
                        }
                    }
                }
            }
        }

        if (showToc) {
            EinkCard(
                modifier = Modifier
                    .fillMaxSize()
                    .align(Alignment.Center),
            ) {
                Column(modifier = Modifier.fillMaxSize()) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(10.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = "目录 (${state.chapters.size})",
                            style = MaterialTheme.typography.titleSmall,
                        )
                        OutlinedButton(onClick = { showToc = false }) {
                            Text("关闭")
                        }
                    }
                    HorizontalDivider()

                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(8.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        itemsIndexed(state.chapters, key = { _, chapter -> chapter.idx }) { index, chapter ->
                            val isActive = index == state.activeChapterListIndex
                            if (isActive) {
                                EinkButton(
                                    onClick = { showToc = false },
                                    modifier = Modifier.fillMaxWidth(),
                                ) {
                                    Text("${chapter.idx + 1}. ${chapter.title}")
                                }
                            } else {
                                OutlinedButton(
                                    onClick = {
                                        onOpenChapter(index)
                                        showToc = false
                                    },
                                    modifier = Modifier.fillMaxWidth(),
                                ) {
                                    Text("${chapter.idx + 1}. ${chapter.title}")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}