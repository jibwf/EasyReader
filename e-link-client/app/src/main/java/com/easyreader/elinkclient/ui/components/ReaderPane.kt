package com.easyreader.elinkclient.ui.components

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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.easyreader.elinkclient.core.EinkDeviceRefreshBridge
import com.easyreader.elinkclient.core.RefreshAction
import com.easyreader.elinkclient.ui.AutoPageTurnSpeed
import com.easyreader.elinkclient.ui.EinkUiState
import com.easyreader.elinkclient.ui.ReaderHardwareAction
import com.easyreader.elinkclient.ui.ReaderFontStyle
import java.io.File
import kotlinx.coroutines.delay
import kotlin.math.roundToInt

@Composable
fun ReaderPane(
    state: EinkUiState,
    onOpenChapter: (Int) -> Unit,
    onPrevChapter: () -> Unit,
    onNextChapter: () -> Unit,
    onUpdateChapterPosition: (Double) -> Unit,
    onPauseAutoTurn: (String?) -> Unit,
    onToggleAutoTurn: () -> Unit,
    onSetAutoTurnSpeed: (AutoPageTurnSpeed) -> Unit,
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

    fun turnPage(forward: Boolean, initiatedByAuto: Boolean = false) {
        if (!initiatedByAuto && state.autoPageTurnEnabled) {
            onPauseAutoTurn("手动翻页已暂停自动模式")
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
                if (initiatedByAuto) {
                    onPauseAutoTurn("自动翻页到章节末尾，已暂停")
                }
                onNextChapter()
                return
            }
            val targetScroll = (currentScroll + viewportHeight).coerceAtMost(maxScroll)
            if (targetScroll == currentScroll) {
                if (initiatedByAuto) {
                    onPauseAutoTurn("自动翻页到章节末尾，已暂停")
                }
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
        if (state.autoPageTurnEnabled) {
            onPauseAutoTurn("打开菜单已暂停自动翻页")
        }
        showQuickMenu = true
    }

    LaunchedEffect(
        state.autoPageTurnEnabled,
        state.autoPageTurnSpeed,
        state.chapterType,
        state.activeChapterListIndex,
        state.chapterText,
    ) {
        if (!state.autoPageTurnEnabled || state.chapterType != "novel") {
            return@LaunchedEffect
        }

        while (state.autoPageTurnEnabled) {
            delay(state.autoPageTurnSpeed.intervalMs)
            if (!state.autoPageTurnEnabled) {
                break
            }
            turnPage(forward = true, initiatedByAuto = true)
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
            .background(MaterialTheme.colorScheme.background)
            .padding(horizontal = 10.dp, vertical = 6.dp),
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            Box(
                modifier = Modifier
                    .fillMaxSize(),
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
                                        onPauseAutoTurn("请求缓存已暂停自动翻页")
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
                                addView(
                                    TextView(context).apply {
                                        includeFontPadding = false
                                        setPadding(0, 4, 0, 16)
                                        setTextColor(readerTextColor)
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
                            scrollView.setOnScrollChangeListener { view, _, _, _, _ ->
                                if (state.chapterType == "novel" && state.activeChapterCached) {
                                    val scrollingView = view as? ScrollView ?: return@setOnScrollChangeListener
                                    val contentView = scrollingView.getChildAt(0) as? TextView ?: return@setOnScrollChangeListener
                                    latestPositionCallback(calculateReadingPosition(scrollingView, contentView))
                                }
                            }
                            textView.text = state.chapterText
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
                                onPauseAutoTurn("打开目录已暂停自动翻页")
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
                        AutoPageTurnSpeed.entries.forEach { speed ->
                            val selected = speed == state.autoPageTurnSpeed
                            if (selected) {
                                EinkButton(
                                    onClick = { onSetAutoTurnSpeed(speed) },
                                    modifier = Modifier.weight(1f),
                                ) {
                                    Text("速度 ${speed.label}")
                                }
                            } else {
                                OutlinedButton(
                                    onClick = { onSetAutoTurnSpeed(speed) },
                                    modifier = Modifier.weight(1f),
                                ) {
                                    Text("速度 ${speed.label}")
                                }
                            }
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
                                        onPauseAutoTurn("目录跳转已暂停自动翻页")
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