package com.easyreader.elinkclient.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.easyreader.elinkclient.ui.components.BookshelfPane
import com.easyreader.elinkclient.ui.components.EinkCard
import com.easyreader.elinkclient.ui.components.HomePane
import com.easyreader.elinkclient.ui.components.ReaderPane
import com.easyreader.elinkclient.ui.components.SearchPane
import com.easyreader.elinkclient.ui.components.SettingsPane

internal enum class ScreenTab(val label: String) {
    Home("首页"),
    Bookshelf("书架"),
    Search("搜索"),
    Settings("设置"),
}

internal fun resolveScreenTab(name: String): ScreenTab {
    return ScreenTab.entries.firstOrNull { it.name == name } ?: ScreenTab.Home
}

@Composable
fun MainScreen(viewModel: EinkViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val lifecycleOwner = LocalLifecycleOwner.current
    var currentTabName by rememberSaveable { mutableStateOf(ScreenTab.Home.name) }
    var showReader by rememberSaveable { mutableStateOf(false) }

    LaunchedEffect(state.activeBookKey) {
        if (state.activeBookKey.isNullOrBlank()) {
            showReader = false
        }
    }

    LaunchedEffect(showReader) {
        viewModel.setReaderVisible(showReader)
    }

    val selectedTab = resolveScreenTab(currentTabName)

    LaunchedEffect(selectedTab, showReader) {
        if (!showReader && (selectedTab == ScreenTab.Home || selectedTab == ScreenTab.Bookshelf)) {
            viewModel.autoSyncServerDataIfNeeded()
        }
    }

    DisposableEffect(lifecycleOwner, showReader) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME && !showReader) {
                viewModel.autoSyncServerDataIfNeeded(force = true)
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        containerColor = if (showReader) Color.White else MaterialTheme.colorScheme.background,
        topBar = {
            if (!showReader) {
                Surface(
                    color = MaterialTheme.colorScheme.surface,
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                    tonalElevation = 0.dp,
                    shadowElevation = 0.dp,
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 10.dp),
                    ) {
                        Row(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = "EasyReader",
                                    style = MaterialTheme.typography.titleLarge,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = if (state.isLoading) "状态: 同步中" else "状态: 就绪",
                            style = MaterialTheme.typography.labelMedium,
                        )
                    }
                }
            }
        },
        bottomBar = {
            if (!showReader) {
                Surface(
                    color = MaterialTheme.colorScheme.surface,
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                    tonalElevation = 0.dp,
                    shadowElevation = 0.dp,
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 8.dp, vertical = 8.dp),
                    ) {
                        ScreenTab.entries.forEach { tab ->
                            val selected = tab == selectedTab
                            OutlinedButton(
                                onClick = { currentTabName = tab.name },
                                modifier = Modifier
                                    .weight(1f)
                                    .height(42.dp)
                                    .padding(horizontal = 2.dp),
                                border = BorderStroke(
                                    width = 1.dp,
                                    color = if (selected) {
                                        MaterialTheme.colorScheme.onBackground
                                    } else {
                                        MaterialTheme.colorScheme.outlineVariant
                                    },
                                ),
                            ) {
                                Text(
                                    text = tab.label,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }
                        }
                    }
                }
            }
        },
    ) { innerPadding ->
        if (showReader) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding),
            ) {
                ReaderPane(
                    state = state,
                    onOpenChapter = viewModel::openChapter,
                    onPrevChapter = viewModel::prevChapter,
                    onNextChapter = viewModel::nextChapter,
                    onUpdateChapterPosition = viewModel::updateActiveChapterPosition,
                    onToggleAutoTurn = viewModel::toggleAutoPageTurn,
                    onIncreaseAutoTurnSpeed = viewModel::increaseAutoPageTurnSpeed,
                    onDecreaseAutoTurnSpeed = viewModel::decreaseAutoPageTurnSpeed,
                    onCycleReaderFont = viewModel::cycleReaderFontStyle,
                    onIncreaseFontSize = viewModel::increaseReaderFontSize,
                    onDecreaseFontSize = viewModel::decreaseReaderFontSize,
                    onIncreaseLineSpacing = viewModel::increaseReaderLineSpacing,
                    onDecreaseLineSpacing = viewModel::decreaseReaderLineSpacing,
                    onRequestCacheCurrentBook = viewModel::refreshActiveBookCache,
                    onExitReader = {
                        viewModel.persistCurrentReadingProgress()
                        viewModel.pauseAutoPageTurn("退出阅读已暂停自动翻页")
                        showReader = false
                    },
                )

                if (state.syncConflictDialogVisible) {
                    state.syncConflict?.let { conflict ->
                    AlertDialog(
                        onDismissRequest = {},
                        tonalElevation = 0.dp,
                        properties = DialogProperties(
                            dismissOnBackPress = false,
                            dismissOnClickOutside = false,
                        ),
                        title = { Text("同步冲突待处理") },
                        text = {
                            Column(verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
                                Text(conflict.summary, style = MaterialTheme.typography.bodySmall)
                                Text(
                                    text = "本地 -> 第 ${conflict.local.chapterIdx + 1} 章 · 位置 ${"%.2f".format(conflict.local.position)}",
                                    style = MaterialTheme.typography.bodySmall,
                                )
                                Text(
                                    text = "云端 -> 第 ${conflict.remote.chapterIdx + 1} 章 · 位置 ${"%.2f".format(conflict.remote.position)}",
                                    style = MaterialTheme.typography.bodySmall,
                                )
                            }
                        },
                        confirmButton = {
                            Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
                                TextButton(onClick = viewModel::resolveSyncConflictUseRemote) {
                                    Text("采用云端")
                                }
                                TextButton(onClick = viewModel::forceSyncConflictLocal) {
                                    Text("采用本地")
                                }
                            }
                        },
                    )
                    }
                }
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .padding(horizontal = 12.dp, vertical = 8.dp),
            ) {
                state.errorMessage?.let { errorText ->
                    EinkCard(modifier = Modifier.fillMaxWidth()) {
                        Text(
                            text = errorText,
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(10.dp),
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                }

                if (state.isLoading) {
                    Text(
                        text = "状态: 任务处理中，请稍候",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                }

                when (selectedTab) {
                    ScreenTab.Home -> {
                        HomePane(
                            state = state,
                            onContinueReading = {
                                if (viewModel.continueReadingFromSession()) {
                                    showReader = true
                                } else {
                                    currentTabName = ScreenTab.Bookshelf.name
                                }
                            },
                            onOpenLocalBookshelf = { currentTabName = ScreenTab.Bookshelf.name },
                            onOpenServerBookshelf = {
                                currentTabName = ScreenTab.Bookshelf.name
                                viewModel.refreshServerBooks(showLoading = false)
                                viewModel.refreshBookCategories(showLoading = false)
                            },
                            onOpenSearch = { currentTabName = ScreenTab.Search.name },
                            onSyncServerData = {
                                viewModel.refreshServerBooks()
                            },
                            onRefreshLocalShelf = viewModel::refreshLocalBookshelf,
                        )
                    }

                    ScreenTab.Bookshelf -> {
                        BookshelfPane(
                            state = state,
                            onSelectCategory = viewModel::setSelectedCategory,
                            onSyncServerData = {
                                viewModel.refreshServerBooks()
                                viewModel.refreshBookCategories()
                            },
                            onRefreshLocalShelf = viewModel::refreshLocalBookshelf,
                            onOpenLocalBook = {
                                showReader = true
                                viewModel.openLocalBook(it)
                            },
                            onOfflineLocalBook = viewModel::refreshLocalBookCache,
                            onDeleteLocalBook = viewModel::deleteLocalBook,
                            onOpenServerBook = {
                                showReader = true
                                viewModel.openServerBook(it)
                            },
                            onOfflineServerBook = viewModel::offlineServerBookToDevice,
                            onQueueOfflineTask = viewModel::queueOfflineTaskForBook,
                        )
                    }

                    ScreenTab.Search -> {
                        SearchPane(
                            state = state,
                            onSearchKeywordChanged = viewModel::updateSearchKeyword,
                            onSearchBooks = viewModel::searchBooksFromServer,
                            onImportSearchResult = viewModel::importSearchResultToDevice,
                        )
                    }

                    ScreenTab.Settings -> {
                        SettingsPane(
                            state = state,
                            onApplyConfig = viewModel::updateServerConfig,
                            onCycleSyncMode = viewModel::cycleSyncMode,
                            onManualSyncProgress = viewModel::manualSyncProgressNow,
                            onResolveSyncConflictUseRemote = viewModel::resolveSyncConflictUseRemote,
                            onForceSyncConflictLocal = viewModel::forceSyncConflictLocal,
                            onRefreshOfflineDiagnostics = viewModel::refreshOfflineCatalog,
                            onPullRemoteProgress = viewModel::pullRemoteProgress,
                            onPullServerBookshelf = viewModel::pullServerBookshelfNow,
                            onCycleRefreshMode = viewModel::cycleRefreshMode,
                            onRefreshCacheStats = viewModel::refreshCacheStats,
                            onClearServerCache = viewModel::clearServerCache,
                            onApplyReaderFont = viewModel::applyReaderFont,
                            onDownloadAndApplyFont = viewModel::downloadAndApplyReaderFont,
                            onDeleteLocalFont = viewModel::deleteLocalReaderFont,
                            onRefreshFonts = viewModel::refreshReaderFonts,
                            onClearClientCache = viewModel::clearClientCache,
                            onCancelOfflineDownload = viewModel::cancelOfflineDownload,
                            onClearError = viewModel::clearError,
                            onLogin = viewModel::loginWithPassword,
                            onLogout = viewModel::logout,
                        )
                    }
                }
            }
        }
    }
}
