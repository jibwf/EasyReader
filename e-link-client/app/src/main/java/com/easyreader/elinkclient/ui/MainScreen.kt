package com.easyreader.elinkclient.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.easyreader.elinkclient.ui.components.BookshelfPane
import com.easyreader.elinkclient.ui.components.HomePane
import com.easyreader.elinkclient.ui.components.ReaderPane
import com.easyreader.elinkclient.ui.components.SearchPane
import com.easyreader.elinkclient.ui.components.SettingsPane

private enum class ScreenTab(val label: String) {
    Home("首页"),
    Bookshelf("书架"),
    Search("搜索"),
    Settings("设置"),
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

    val selectedTab = ScreenTab.valueOf(currentTabName)

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
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            if (!showReader) {
                Surface(
                    color = MaterialTheme.colorScheme.surface,
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
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
                    onPauseAutoTurn = viewModel::pauseAutoPageTurn,
                    onToggleAutoTurn = viewModel::toggleAutoPageTurn,
                    onCycleReaderFont = viewModel::cycleReaderFontStyle,
                    onIncreaseFontSize = viewModel::increaseReaderFontSize,
                    onDecreaseFontSize = viewModel::decreaseReaderFontSize,
                    onIncreaseLineSpacing = viewModel::increaseReaderLineSpacing,
                    onDecreaseLineSpacing = viewModel::decreaseReaderLineSpacing,
                    onExitReader = {
                        viewModel.pauseAutoPageTurn("退出阅读已暂停自动翻页")
                        showReader = false
                    },
                )
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .padding(horizontal = 12.dp, vertical = 8.dp),
            ) {
                state.errorMessage?.let { errorText ->
                    Card(modifier = Modifier.fillMaxWidth()) {
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
                                if (!state.activeBookKey.isNullOrBlank()) {
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
                                viewModel.refreshOfflineCatalog(showLoading = false)
                            },
                            onOpenSearch = { currentTabName = ScreenTab.Search.name },
                            onSyncServerData = {
                                viewModel.refreshServerBooks()
                                viewModel.refreshOfflineCatalog()
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
                                viewModel.refreshOfflineCatalog()
                            },
                            onRefreshLocalShelf = viewModel::refreshLocalBookshelf,
                            onOpenOfflineBook = {
                                showReader = true
                                viewModel.openOfflineBook(it)
                            },
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
                            onPullRemoteProgress = viewModel::pullRemoteProgress,
                            onPullServerBookshelf = viewModel::pullServerBookshelfNow,
                            onCycleRefreshMode = viewModel::cycleRefreshMode,
                            onToggleAutoPageTurn = viewModel::toggleAutoPageTurn,
                            onSetAutoPageTurnSpeed = viewModel::setAutoPageTurnSpeed,
                            onRefreshCacheStats = viewModel::refreshCacheStats,
                            onClearServerCache = viewModel::clearServerCache,
                            onApplyReaderFont = viewModel::applyReaderFont,
                            onDownloadAndApplyFont = viewModel::downloadAndApplyReaderFont,
                            onDeleteLocalFont = viewModel::deleteLocalReaderFont,
                            onRefreshFonts = viewModel::refreshReaderFonts,
                            onClearClientCache = viewModel::clearClientCache,
                            onCancelOfflineDownload = viewModel::cancelOfflineDownload,
                            onClearError = viewModel::clearError,
                        )
                    }
                }
            }
        }
    }
}
