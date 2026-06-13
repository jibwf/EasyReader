package com.easyreader.elinkclient.ui

import android.app.Application
import android.content.Context
import android.view.KeyEvent
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.CreationExtras
import androidx.lifecycle.viewModelScope
import com.easyreader.elinkclient.core.AppConfig
import com.easyreader.elinkclient.core.BookIdentity
import com.easyreader.elinkclient.core.DeviceIdProvider
import com.easyreader.elinkclient.core.EinkRefreshPolicy
import com.easyreader.elinkclient.core.NetworkDisabledException
import com.easyreader.elinkclient.core.NetworkGate
import com.easyreader.elinkclient.core.RefreshAction
import com.easyreader.elinkclient.core.WifiConnectivityMonitor
import com.easyreader.elinkclient.data.model.BookCategoryItem
import com.easyreader.elinkclient.data.model.BookItem
import com.easyreader.elinkclient.data.model.ChapterItem
import com.easyreader.elinkclient.data.model.ClientCacheStats
import com.easyreader.elinkclient.data.model.LocalShelfBook
import com.easyreader.elinkclient.data.model.OfflineTaskCreateRequest
import com.easyreader.elinkclient.data.model.OfflineTaskItem
import com.easyreader.elinkclient.data.model.SearchResultItem
import com.easyreader.elinkclient.data.model.ServerCacheStats
import com.easyreader.elinkclient.data.model.ServerFontItem
import com.easyreader.elinkclient.data.model.SyncProgressItem
import com.easyreader.elinkclient.data.model.SyncProgressUpsertRequest
import com.easyreader.elinkclient.data.offline.OfflineDownloadManager
import com.easyreader.elinkclient.data.offline.OfflineDownloadResult
import com.easyreader.elinkclient.data.repository.ReaderRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.math.ceil
import kotlin.math.floor
import org.json.JSONArray
import org.json.JSONObject

class EinkViewModel(application: Application) : AndroidViewModel(application) {
    private val builtInFontOptions = listOf(
        ReaderFontOption(
            key = "builtin:serif",
            name = "系统衬线",
            fromServer = false,
            downloaded = true,
        ),
        ReaderFontOption(
            key = "builtin:sans",
            name = "系统无衬线",
            fromServer = false,
            downloaded = true,
        ),
    )

    private val networkGate = NetworkGate(application)
    private val repository = ReaderRepository(application, networkGate = networkGate)
    private val offlineDownloadManager = OfflineDownloadManager(repository)
    private val wifiMonitor = WifiConnectivityMonitor(application)
    private val prefs = application.getSharedPreferences(AppConfig.PREFS_NAME, Context.MODE_PRIVATE)
    private val refreshPolicy =
        EinkRefreshPolicy(
            initialMode = EinkRefreshPolicy.detectDefaultMode(),
        )

    private var wifiFullSyncJob: Job? = null
    private var serverOfflineTaskMonitorJob: Job? = null
    private var backgroundBookCacheJob: Job? = null
    private var backgroundBookCacheBookKey: String? = null
    private var deferredCacheStatsJob: Job? = null
    private var deferredLocalBookshelfJob: Job? = null
    private var startupFirstScreenDisplayed = false
    private var lastProgressSyncAtMs = 0L
    private val progressSyncCooldownMs = 45_000L
    private val pendingSyncQueue = LinkedHashMap<String, SyncProgressUpsertRequest>()
    private val chapterChunkSizeChars = 36_000
    private val progressConflictThreshold = 0.30

    private val _state =
        MutableStateFlow(
            EinkUiState(
                refreshMode = refreshPolicy.mode,
                refreshEveryTurns = refreshPolicy.mode.fullRefreshInterval,
            )
        )

    val state: StateFlow<EinkUiState> = _state.asStateFlow()

    init {
        val deviceId = DeviceIdProvider(application).getOrCreate()
        val savedBaseUrl = prefs.getString(AppConfig.KEY_BASE_URL, AppConfig.DEFAULT_BASE_URL)
            ?: AppConfig.DEFAULT_BASE_URL
        val savedUserId = prefs.getString(AppConfig.KEY_USER_ID, AppConfig.DEFAULT_USER_ID)
            ?: AppConfig.DEFAULT_USER_ID
        val savedFontStyle = prefs.getString(AppConfig.KEY_READER_FONT_STYLE, ReaderFontStyle.SERIF.name)
            ?.let { name -> ReaderFontStyle.entries.firstOrNull { it.name == name } }
            ?: ReaderFontStyle.SERIF
        val savedFontKey = prefs.getString(AppConfig.KEY_READER_FONT_KEY, null)
            ?: if (savedFontStyle == ReaderFontStyle.SANS) "builtin:sans" else "builtin:serif"
        val savedFontSizeSp = prefs.getInt(AppConfig.KEY_READER_FONT_SIZE, 30).coerceIn(18, 36)
        val savedLineSpacing = prefs.getFloat(AppConfig.KEY_READER_LINE_SPACING, 1.2f).let { spacing ->
            if (spacing.isFinite() && spacing > 0f) spacing else 1.2f
        }
        val savedAutoTurnIntervalMs = AutoPageTurnSpeedConfig.fromStorage(
            prefs.getString(AppConfig.KEY_READER_AUTO_TURN_SPEED, null)
        )
        val savedSyncMode = SyncMode.fromStorage(prefs.getString(AppConfig.KEY_SYNC_POLICY, null))
        val restoredSession = loadLastActiveReadingSession()
        val networkAvailable = networkGate.canUseNetwork()
        pendingSyncQueue.clear()
        pendingSyncQueue.putAll(loadPendingSyncQueue())

        repository.updateBaseUrl(savedBaseUrl)
        val startupMessage = when {
            restoredSession != null -> "已恢复上次阅读会话，点击继续阅读后加载内容"
            networkAvailable -> "WiFi 已连接，等待首屏完成后同步"
            else -> "WiFi 未连接，离线阅读模式"
        }
        _state.value = _state.value.copy(
            baseUrl = repository.getCurrentBaseUrl(),
            userId = savedUserId,
            deviceId = deviceId,
            networkMode = networkModeFor(networkAvailable),
            syncMode = savedSyncMode,
            isNetworkAvailable = networkAvailable,
            readerFontStyle = savedFontStyle,
            readerFontKey = savedFontKey,
            readerFonts = builtInFontOptions,
            readerFontSizeSp = savedFontSizeSp,
            readerLineSpacing = savedLineSpacing,
            autoPageTurnIntervalMs = savedAutoTurnIntervalMs,
            pendingSyncCount = pendingSyncQueue.size,
            refreshMode = refreshPolicy.mode,
            refreshEveryTurns = refreshPolicy.mode.fullRefreshInterval,
            activeBookName = restoredSession?.bookName.orEmpty(),
            activeBookKey = restoredSession?.bookKey,
            activeBookUrl = restoredSession?.bookUrl,
            activeSourceUrl = restoredSession?.sourceUrl,
            activeChapterPosition = restoredSession?.position ?: 0.0,
            activeChapterScrollPosition = restoredSession?.position ?: 0.0,
            readingChapterByBook = restoredSession?.let {
                mapOf(it.bookKey to it.chapterNumber)
            } ?: emptyMap(),
            readingPositionByBook = restoredSession?.let {
                mapOf(it.bookKey to it.position)
            } ?: emptyMap(),
            lastSyncMessage = startupMessage,
        )
        wifiMonitor.start()
        observeWifiConnectivity()
        checkAuthState()
    }

    override fun onCleared() {
        wifiFullSyncJob?.cancel()
        serverOfflineTaskMonitorJob?.cancel()
        backgroundBookCacheJob?.cancel()
        deferredCacheStatsJob?.cancel()
        deferredLocalBookshelfJob?.cancel()
        offlineDownloadManager.cancel()
        repository.cancelNetworkRequests()
        wifiMonitor.stop()
        super.onCleared()
    }

    fun updateServerConfig(baseUrlInput: String, userIdInput: String) {
        val normalizedBaseUrl = ReaderRepository.normalizeBaseUrl(baseUrlInput)
        val normalizedUserId = userIdInput.trim().ifBlank { AppConfig.DEFAULT_USER_ID }
        val previousUserId = _state.value.userId

        prefs.edit()
            .putString(AppConfig.KEY_BASE_URL, normalizedBaseUrl)
            .putString(AppConfig.KEY_USER_ID, normalizedUserId)
            .apply()

        repository.updateBaseUrl(normalizedBaseUrl)
        serverOfflineTaskMonitorJob?.cancel()

        _state.update {
            val networkAvailable = networkGate.canUseNetwork()
            it.copy(
                baseUrl = normalizedBaseUrl,
                userId = normalizedUserId,
                errorMessage = null,
                isNetworkAvailable = networkAvailable,
                networkMode = networkModeFor(networkAvailable),
                offlineTasks = emptyList(),
                activeOfflineTask = null,
                offlineTaskStatusMessage = "",
                lastSyncMessage = "配置已保存",
            )
        }

        if (previousUserId != normalizedUserId) {
            clearLastActiveReadingSession()
            _state.update {
                it.copy(
                    activeBookName = "",
                    activeBookKey = null,
                    activeBookUrl = null,
                    activeSourceUrl = null,
                    chapters = emptyList(),
                    activeChapterListIndex = 0,
                    activeChapterCached = false,
                    activeChapterTitle = "",
                    activeChapterPosition = 0.0,
                    activeChapterScrollPosition = 0.0,
                    chapterText = "",
                    readingChapterByBook = emptyMap(),
                    readingPositionByBook = emptyMap(),
                    remoteReadingChapterByBook = emptyMap(),
                    remoteReadingPositionByBook = emptyMap(),
                )
            }
            clearPendingSyncQueue("用户切换，待补传队列已清空")
            clearSyncConflict("用户切换，已清除同步冲突")
        }

        refreshLocalBookshelf(showLoading = false)
        refreshCacheStats(showLoading = false)
        if (networkGate.canUseNetwork()) {
            scheduleWifiFullSync("配置更新")
        }
    }

    fun loginWithPassword(password: String) {
        if (password.isBlank()) return
        viewModelScope.launch {
            _state.update { it.copy(authMessage = "登录中...") }
            try {
                val response = repository.login(password, android.os.Build.MODEL)
                val token = response.token
                prefs.edit().putString(AppConfig.KEY_AUTH_TOKEN, token).apply()
                com.easyreader.elinkclient.data.network.NetworkModule.setAuthToken(token)
                _state.update {
                    it.copy(
                        authToken = token,
                        authMessage = "登录成功，正在同步...",
                    )
                }
                if (networkGate.canUseNetwork()) {
                    scheduleWifiFullSync("登录成功")
                }
                _state.update {
                    it.copy(authMessage = "登录成功，${response.expiresInDays} 天内无需重新输入")
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(authMessage = "登录失败: ${e.message ?: "未知错误"}")
                }
            }
        }
    }

    fun logout() {
        prefs.edit().remove(AppConfig.KEY_AUTH_TOKEN).apply()
        com.easyreader.elinkclient.data.network.NetworkModule.setAuthToken("")
        _state.update {
            it.copy(
                authToken = "",
                authMessage = "已退出登录",
            )
        }
    }

    fun checkAuthState() {
        val savedToken = prefs.getString(AppConfig.KEY_AUTH_TOKEN, null)
        if (savedToken.isNullOrBlank()) return
        com.easyreader.elinkclient.data.network.NetworkModule.setAuthToken(savedToken)
        viewModelScope.launch {
            try {
                val valid = repository.verifyToken(savedToken)
                if (valid) {
                    _state.update { it.copy(authToken = savedToken) }
                } else {
                    prefs.edit().remove(AppConfig.KEY_AUTH_TOKEN).apply()
                    com.easyreader.elinkclient.data.network.NetworkModule.setAuthToken("")
                    _state.update { it.copy(authToken = "", authMessage = "Token 已过期，请重新登录") }
                }
            } catch (e: Exception) {
                _state.update { it.copy(authToken = savedToken) }
            }
        }
    }

    fun createCategory(name: String) {
        if (name.isBlank()) return
        viewModelScope.launch {
            try {
                repository.createBookCategory(name)
                _state.update { it.copy(categoryMessage = "已创建分类: $name") }
                refreshCategories()
            } catch (e: Exception) {
                _state.update { it.copy(categoryMessage = "创建分类失败: ${e.message}") }
            }
        }
    }

    fun toggleCategoryHidden(categoryName: String, hidden: Boolean) {
        viewModelScope.launch {
            try {
                repository.toggleCategoryHidden(categoryName, hidden)
                _state.update { state ->
                    val updatedCategories = state.bookCategories.map { category ->
                        if (category.name == categoryName) {
                            category.copy(hidden = hidden)
                        } else {
                            category
                        }
                    }
                    state.copy(
                        bookCategories = updatedCategories,
                        categoryMessage = if (hidden) "已隐藏分类: $categoryName" else "已取消隐藏: $categoryName",
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(categoryMessage = "操作失败: ${e.message}") }
            }
        }
    }

    fun renameCategory(oldName: String, newName: String) {
        if (oldName.isBlank() || newName.isBlank()) return
        viewModelScope.launch {
            try {
                repository.renameBookCategory(oldName, newName)
                _state.update { it.copy(categoryMessage = "已重命名: $oldName -> $newName") }
                refreshCategories()
            } catch (e: Exception) {
                _state.update { it.copy(categoryMessage = "重命名失败: ${e.message}") }
            }
        }
    }

    fun deleteCategory(categoryName: String) {
        viewModelScope.launch {
            try {
                repository.deleteBookCategory(categoryName)
                _state.update { it.copy(categoryMessage = "已删除分类: $categoryName") }
                refreshCategories()
            } catch (e: Exception) {
                _state.update { it.copy(categoryMessage = "删除失败: ${e.message}") }
            }
        }
    }

    private fun refreshCategories() {
        viewModelScope.launch {
            try {
                val categories = repository.getBookCategories()
                _state.update { it.copy(bookCategories = categories) }
            } catch (e: Exception) {
                // ignore
            }
        }
    }

    fun refreshServerBooks(showLoading: Boolean = true) {
        runRequest(
            block = { repository.getBooks() },
            onSuccess = { books ->
                _state.update {
                    it.copy(
                        isLoading = if (showLoading) false else it.isLoading,
                        errorMessage = null,
                        serverBooks = books,
                        lastSyncMessage = "服务器书架已刷新：${books.size} 本",
                    )
                }
            },
            onErrorPrefix = "刷新服务器书架失败",
            showLoading = showLoading,
        )
    }

    fun refreshBookCategories(showLoading: Boolean = false) {
        runRequest(
            block = { repository.getBookCategories() },
            onSuccess = { categories ->
                _state.update { state ->
                    val selected = if (state.selectedCategory == "all") {
                        "all"
                    } else if (categories.any { it.name == state.selectedCategory }) {
                        state.selectedCategory
                    } else {
                        "all"
                    }
                    state.copy(
                        isLoading = if (showLoading) false else state.isLoading,
                        errorMessage = null,
                        bookCategories = categories,
                        selectedCategory = selected,
                    )
                }
            },
            onErrorPrefix = "刷新服务器分类失败",
            showLoading = showLoading,
        )
    }

    fun setSelectedCategory(category: String) {
        _state.update { it.copy(selectedCategory = category.trim().ifBlank { "all" }) }
    }

    fun setServerBookCategory(book: BookItem, categoryName: String) {
        val normalized = categoryName.trim()
        if (normalized.isBlank()) {
            return
        }
        runRequest(
            block = { repository.setBookCategory(book.id, normalized) },
            onSuccess = {
                _state.update { state ->
                    state.copy(
                        isLoading = false,
                        errorMessage = null,
                        serverBooks = state.serverBooks.map { item ->
                            if (item.id == book.id) item.copy(categoryName = normalized) else item
                        },
                        localBookshelf = state.localBookshelf.map { item ->
                            if (item.bookUrl == book.bookUrl && item.sourceUrl == book.sourceUrl) {
                                item.copy(categoryName = normalized)
                            } else {
                                item
                            }
                        },
                        lastSyncMessage = "${book.name} 分类已更新为 $normalized",
                    )
                }
                refreshBookCategories(showLoading = false)
            },
            onErrorPrefix = "更新分类失败",
            showLoading = false,
        )
    }

    fun refreshReaderFonts(showLoading: Boolean = false) {
        runRequest(
            block = {
                val serverFonts = repository.getServerFonts()
                val localPaths = repository.listDownloadedFontFiles()
                serverFonts to localPaths
            },
            onSuccess = { (serverFonts, localPaths) ->
                val options = buildReaderFontOptions(serverFonts, localPaths)
                _state.update { state ->
                    val selected = options.firstOrNull { it.key == state.readerFontKey } ?: options.first()
                    val style = resolveReaderFontStyle(selected.key)
                    prefs.edit()
                        .putString(AppConfig.KEY_READER_FONT_KEY, selected.key)
                        .putString(AppConfig.KEY_READER_FONT_STYLE, style.name)
                        .apply()
                    state.copy(
                        isLoading = if (showLoading) false else state.isLoading,
                        errorMessage = null,
                        readerFonts = options,
                        readerFontKey = selected.key,
                        readerFontPath = selected.filePath,
                        readerFontStyle = style,
                        lastSyncMessage = "字体列表已刷新：服务器 ${serverFonts.size} 个，本地 ${localPaths.size} 个",
                    )
                }
            },
            onErrorPrefix = "刷新字体失败",
            showLoading = showLoading,
        )
    }

    fun refreshCacheStats(showLoading: Boolean = false) {
        val networkAvailable = refreshNetworkAvailability()
        runRequest(
            block = {
                val clientStats = repository.getClientCacheStats()
                val serverStats = if (networkAvailable) {
                    repository.getServerCacheStats()
                } else {
                    _state.value.serverCacheStats
                }
                serverStats to clientStats
            },
            onSuccess = { (serverStats, clientStats) ->
                _state.update {
                    it.copy(
                        isLoading = if (showLoading) false else it.isLoading,
                        errorMessage = null,
                        serverCacheStats = serverStats,
                        clientCacheStats = clientStats,
                        serverCacheMessage = if (!networkAvailable) "离线模式：仅刷新本地缓存统计" else it.serverCacheMessage,
                    )
                }
            },
            onErrorPrefix = "刷新缓存统计失败",
            showLoading = showLoading,
        )
    }

    private fun refreshCacheStatsDeferred(delayMs: Long = 2_000L) {
        deferredCacheStatsJob?.cancel()
        deferredCacheStatsJob = viewModelScope.launch {
            if (delayMs > 0L) {
                delay(delayMs)
            }
            refreshCacheStats(showLoading = false)
        }
    }

    fun clearServerCache() {
        runRequest(
            block = {
                val cleared = repository.clearServerCache(clearAll = true)
                val latest = repository.getServerCacheStats()
                cleared to latest
            },
            onSuccess = { (clearResult, latest) ->
                _state.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = null,
                        serverCacheStats = latest,
                        serverCacheMessage = "服务器缓存已清理：删除 ${clearResult.cleared} 条",
                    )
                }
            },
            onErrorPrefix = "清理服务器缓存失败",
        )
    }

    fun applyReaderFont(fontKey: String) {
        val selected = _state.value.readerFonts.firstOrNull { it.key == fontKey } ?: return
        if (selected.fromServer && !selected.downloaded) {
            _state.update { it.copy(errorMessage = "字体尚未下载") }
            return
        }
        val style = resolveReaderFontStyle(selected.key)
        prefs.edit()
            .putString(AppConfig.KEY_READER_FONT_KEY, selected.key)
            .putString(AppConfig.KEY_READER_FONT_STYLE, style.name)
            .apply()
        _state.update {
            it.copy(
                readerFontKey = selected.key,
                readerFontPath = selected.filePath,
                readerFontStyle = style,
                lastSyncMessage = "字体已切换：${selected.name}",
            )
        }
        applyRefreshAction(RefreshAction.FULL)
    }

    fun downloadAndApplyReaderFont(font: ServerFontItem) {
        runRequest(
            block = {
                repository.downloadServerFont(font)
                val serverFonts = repository.getServerFonts()
                val localPaths = repository.listDownloadedFontFiles()
                buildReaderFontOptions(serverFonts, localPaths)
            },
            onSuccess = { options ->
                _state.update { state ->
                    val selected = options.firstOrNull { it.key == "server:${font.id}" }
                        ?: options.firstOrNull { it.key == state.readerFontKey }
                        ?: options.first()
                    val style = resolveReaderFontStyle(selected.key)
                    prefs.edit()
                        .putString(AppConfig.KEY_READER_FONT_KEY, selected.key)
                        .putString(AppConfig.KEY_READER_FONT_STYLE, style.name)
                        .apply()
                    state.copy(
                        isLoading = false,
                        errorMessage = null,
                        readerFonts = options,
                        readerFontKey = selected.key,
                        readerFontPath = selected.filePath,
                        readerFontStyle = style,
                        lastSyncMessage = "字体已下载并应用：${selected.name}",
                    )
                }
                applyRefreshAction(RefreshAction.FULL)
            },
            onErrorPrefix = "下载字体失败",
        )
    }

    fun deleteLocalReaderFont(filePath: String) {
        if (filePath.isBlank()) {
            return
        }
        runRequest(
            block = {
                repository.deleteLocalFontFile(filePath)
                val serverFonts = if (repository.canUseNetwork()) {
                    runCatching { repository.getServerFonts() }.getOrDefault(emptyList())
                } else {
                    emptyList()
                }
                val localPaths = repository.listDownloadedFontFiles()
                buildReaderFontOptions(serverFonts, localPaths)
            },
            onSuccess = { options ->
                _state.update { state ->
                    val fallback = options.firstOrNull { it.key == "builtin:serif" } ?: options.first()
                    val selected = options.firstOrNull { it.key == state.readerFontKey && it.filePath != filePath } ?: fallback
                    val style = resolveReaderFontStyle(selected.key)
                    prefs.edit()
                        .putString(AppConfig.KEY_READER_FONT_KEY, selected.key)
                        .putString(AppConfig.KEY_READER_FONT_STYLE, style.name)
                        .apply()
                    state.copy(
                        isLoading = false,
                        errorMessage = null,
                        readerFonts = options,
                        readerFontKey = selected.key,
                        readerFontPath = selected.filePath,
                        readerFontStyle = style,
                        lastSyncMessage = "本地字体已删除",
                    )
                }
                applyRefreshAction(RefreshAction.FULL)
            },
            onErrorPrefix = "删除本地字体失败",
            showLoading = false,
        )
    }

    fun autoSyncServerDataIfNeeded(force: Boolean = false) {
        if (force && networkGate.canUseNetwork()) {
            scheduleWifiFullSync("前台恢复")
        }
    }

    fun refreshLocalBookshelf(showLoading: Boolean = true) {
        runRequest(
            block = { repository.getLocalBookshelf() },
            onSuccess = { books ->
                val localChapterMap = books.associate { book ->
                    resolveBookKey(book.bookKey, book.sourceUrl, book.bookUrl) to book.lastReadChapter.coerceAtLeast(1)
                }
                val localPositionMap = books.associate { book ->
                    resolveBookKey(book.bookKey, book.sourceUrl, book.bookUrl) to normalizeReadingPosition(book.lastReadPosition)
                }
                _state.update {
                    it.copy(
                        isLoading = if (showLoading) false else it.isLoading,
                        errorMessage = null,
                        localBookshelf = books,
                        readingChapterByBook = it.readingChapterByBook + localChapterMap,
                        readingPositionByBook = it.readingPositionByBook + localPositionMap,
                    )
                }
            },
            onErrorPrefix = "刷新本地书架失败",
            showLoading = showLoading,
        )
    }

    private fun refreshLocalBookshelfDeferred(delayMs: Long = 0L) {
        deferredLocalBookshelfJob?.cancel()
        deferredLocalBookshelfJob = viewModelScope.launch {
            if (delayMs > 0L) {
                delay(delayMs)
            }
            refreshLocalBookshelf(showLoading = false)
        }
    }

    fun updateSearchKeyword(keyword: String) {
        _state.update { it.copy(searchKeyword = keyword) }
    }

    fun searchBooksFromServer() {
        val keyword = _state.value.searchKeyword.trim()
        if (keyword.isBlank()) {
            _state.update { it.copy(errorMessage = "请输入搜索关键词") }
            return
        }
        runRequest(
            block = { repository.searchBooks(keyword) },
            onSuccess = { results ->
                _state.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = null,
                        searchResults = results,
                        lastSyncMessage = "搜索完成：${results.size} 条结果",
                    )
                }
            },
            onErrorPrefix = "搜索失败",
        )
    }

    fun importSearchResultToDevice(item: SearchResultItem) {
        val identity = getUserAndDevice() ?: return
        runOfflinePipeline(
            prepareBook = {
                repository.addBookToServer(item)
                repository.ensureLocalShelfBook(item)
            },
            createServerTask = { book ->
                repository.createServerOfflineTask(
                    userId = identity.first,
                    deviceId = identity.second,
                    bookKey = book.bookKey,
                    bookUrl = book.bookUrl,
                    sourceUrl = book.sourceUrl,
                )
            },
            operationLabel = "搜索导入并缓存",
        )
    }

    fun addServerBookToLocalShelf(book: BookItem) {
        runRequest(
            block = { repository.ensureLocalShelfBook(book) },
            onSuccess = {
                _state.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = null,
                        lastSyncMessage = "已加入本地书架：${book.name}",
                    )
                }
                refreshLocalBookshelf(showLoading = false)
            },
            onErrorPrefix = "加入本地书架失败",
        )
    }

    fun offlineServerBookToDevice(book: BookItem) {
        val identity = getUserAndDevice() ?: return
        runOfflinePipeline(
            prepareBook = { repository.ensureLocalShelfBook(book) },
            createServerTask = {
                repository.createServerOfflineTask(
                    userId = identity.first,
                    deviceId = identity.second,
                    bookId = book.id,
                    bookKey = book.bookKey,
                )
            },
            operationLabel = "服务器书籍缓存到本地",
        )
    }

    fun offlineLocalShelfBookToDevice(book: LocalShelfBook) {
        val identity = getUserAndDevice() ?: return
        runOfflinePipeline(
            prepareBook = { book },
            createServerTask = {
                repository.createServerOfflineTask(
                    userId = identity.first,
                    deviceId = identity.second,
                    bookKey = book.bookKey,
                    bookUrl = book.bookUrl,
                    sourceUrl = book.sourceUrl,
                )
            },
            operationLabel = "本地书籍更新缓存",
        )
    }

    fun refreshLocalBookCache(book: LocalShelfBook) {
        offlineLocalShelfBookToDevice(book)
    }

    fun cancelOfflineDownload() {
        offlineDownloadManager.cancel()
        repository.cancelNetworkRequests()
        _state.update {
            it.copy(
                offlineDownloadActive = false,
                isLoading = false,
                localCacheStatusMessage = "离线缓存已取消，已完成章节保留",
                lastSyncMessage = "离线缓存已取消",
            )
        }
    }

    fun deleteLocalBook(book: LocalShelfBook) {
        runRequest(
            block = {
                repository.deleteLocalBook(book.bookKey)
                repository.getLocalBookshelf()
            },
            onSuccess = { shelf ->
                _state.update { state ->
                    val deletingActiveBook = state.activeBookKey == book.bookKey
                    state.copy(
                        isLoading = false,
                        errorMessage = null,
                        localBookshelf = shelf,
                        activeBookName = if (deletingActiveBook) "" else state.activeBookName,
                        activeBookKey = if (deletingActiveBook) null else state.activeBookKey,
                        activeBookUrl = if (deletingActiveBook) null else state.activeBookUrl,
                        activeSourceUrl = if (deletingActiveBook) null else state.activeSourceUrl,
                        chapters = if (deletingActiveBook) emptyList() else state.chapters,
                        activeChapterListIndex = if (deletingActiveBook) 0 else state.activeChapterListIndex,
                        activeChapterCached = if (deletingActiveBook) false else state.activeChapterCached,
                        activeChapterTitle = if (deletingActiveBook) "" else state.activeChapterTitle,
                        activeChapterPosition = if (deletingActiveBook) 0.0 else state.activeChapterPosition,
                        activeChapterScrollPosition = if (deletingActiveBook) 0.0 else state.activeChapterScrollPosition,
                        readingChapterByBook = state.readingChapterByBook - book.bookKey,
                        readingPositionByBook = state.readingPositionByBook - book.bookKey,
                        lastSyncMessage = "已删除本地书籍：${book.name}",
                    )
                }
                if (_state.value.activeBookKey == null) {
                    clearLastActiveReadingSession()
                }
                refreshCacheStats(showLoading = false)
            },
            onErrorPrefix = "删除本地书籍失败",
            showLoading = false,
        )
    }

    fun openServerBook(book: BookItem) {
        val existingLocal = _state.value.localBookshelf.firstOrNull { it.bookKey == book.bookKey }
        val preferredChapterNumber = existingLocal?.lastReadChapter?.coerceAtLeast(1) ?: 1
        val preferredPosition = existingLocal?.lastReadPosition ?: 0.0

        persistLastActiveReadingSession(
            bookKey = book.bookKey,
            bookName = book.name,
            bookUrl = book.bookUrl,
            sourceUrl = book.sourceUrl,
            chapterNumber = preferredChapterNumber,
            position = preferredPosition,
        )

        viewModelScope.launch {
            runCatching { repository.ensureLocalShelfBook(book) }
            refreshLocalBookshelf(showLoading = false)
        }
        openBook(
            book.bookKey,
            book.bookUrl,
            book.sourceUrl,
            book.name,
            preferredChapterNumber = preferredChapterNumber,
            preferredPosition = preferredPosition,
        )
    }

    fun openLocalBook(book: LocalShelfBook) {
        val preferredChapterNumber = book.lastReadChapter.coerceAtLeast(1)
        val preferredPosition = normalizeReadingPosition(book.lastReadPosition)

        persistLastActiveReadingSession(
            bookKey = book.bookKey,
            bookName = book.name,
            bookUrl = book.bookUrl,
            sourceUrl = book.sourceUrl,
            chapterNumber = preferredChapterNumber,
            position = preferredPosition,
        )

        _state.update { state ->
            state.copy(
                readingChapterByBook = state.readingChapterByBook + (
                    book.bookKey to preferredChapterNumber
                ),
                readingPositionByBook = state.readingPositionByBook + (
                    book.bookKey to preferredPosition
                ),
            )
        }
        openBook(
            book.bookKey,
            book.bookUrl,
            book.sourceUrl,
            book.name,
            preferredChapterNumber = preferredChapterNumber,
            preferredPosition = preferredPosition,
        )
    }

    fun continueReadingFromSession(): Boolean {
        val snapshot = _state.value
        val bookKey = snapshot.activeBookKey
        val bookUrl = snapshot.activeBookUrl
        val sourceUrl = snapshot.activeSourceUrl

        if (bookKey.isNullOrBlank() || bookUrl.isNullOrBlank() || sourceUrl.isNullOrBlank()) {
            _state.update { it.copy(errorMessage = "当前没有可恢复的阅读会话") }
            return false
        }

        val chapterNumber = snapshot.readingChapterByBook[bookKey]?.coerceAtLeast(1)
            ?: (snapshot.activeChapterListIndex + 1).coerceAtLeast(1)
        val position = snapshot.readingPositionByBook[bookKey] ?: snapshot.activeChapterPosition

        openBook(
            bookKey = bookKey,
            bookUrl = bookUrl,
            sourceUrl = sourceUrl,
            bookName = snapshot.activeBookName.ifBlank { "未命名书籍" },
            preferredChapterNumber = chapterNumber,
            preferredPosition = position,
        )
        return true
    }

    fun queueOfflineTaskForBook(book: BookItem) {
        val snapshot = _state.value
        if (snapshot.userId.isBlank() || snapshot.deviceId.isBlank()) {
            _state.update { it.copy(errorMessage = "缺少用户 ID 或设备 ID") }
            return
        }
        runRequest(
            block = {
                repository.createOfflineTask(
                    OfflineTaskCreateRequest(
                        userId = snapshot.userId,
                        deviceId = snapshot.deviceId,
                        bookId = book.id,
                        bookKey = book.bookKey,
                    )
                )
            },
            onSuccess = { task ->
                _state.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = null,
                        activeOfflineTask = ActiveOfflineTaskState(
                            taskId = task.taskId,
                            bookName = task.bookName,
                            status = task.status,
                            progress = task.progress,
                            cachedChapters = task.cachedChapters,
                            totalChapters = task.totalChapters,
                            errorMessage = task.errorMessage,
                        ),
                        offlineTaskStatusMessage = "服务器缓存任务 ${task.status}：${task.bookName}",
                        lastSyncMessage = "服务器缓存任务 ${task.status}：${task.bookName}",
                    )
                }
                monitorActiveOfflineTask(task, book.name)
            },
            onErrorPrefix = "创建服务器缓存任务失败",
        )
    }

    fun openChapter(chapterListIndex: Int) {
        viewModelScope.launch {
            loadChapterInternal(chapterListIndex, pushProgress = true, restorePosition = 0.0)
        }
    }

    fun nextChapter() {
        val nextIndex = _state.value.activeChapterListIndex + 1
        if (nextIndex <= _state.value.chapters.lastIndex) {
            openChapter(nextIndex)
        }
    }

    fun prevChapter() {
        val prevIndex = _state.value.activeChapterListIndex - 1
        if (prevIndex >= 0) {
            openChapter(prevIndex)
        }
    }

    fun cycleRefreshMode() {
        val mode = refreshPolicy.cycleMode()
        _state.update {
            it.copy(
                refreshMode = mode,
                refreshEveryTurns = mode.fullRefreshInterval,
                lastSyncMessage = "刷新模式：${mode.label}",
            )
        }
        applyRefreshAction(RefreshAction.FULL)
    }

    fun toggleAutoPageTurn() {
        val snapshot = _state.value
        if (snapshot.activeBookKey.isNullOrBlank() || snapshot.chapters.isEmpty()) {
            _state.update { it.copy(lastSyncMessage = "当前没有可自动翻页的阅读会话") }
            return
        }
        if (snapshot.chapterType != "novel") {
            _state.update { it.copy(lastSyncMessage = "漫画模式暂不支持自动翻页") }
            return
        }
        _state.update {
            val nextEnabled = !it.autoPageTurnEnabled
            it.copy(
                autoPageTurnEnabled = nextEnabled,
                lastSyncMessage = if (nextEnabled) {
                    "自动翻页已开启（${AutoPageTurnSpeedConfig.formatLabel(it.autoPageTurnIntervalMs)}）"
                } else {
                    "自动翻页已暂停"
                },
            )
        }
    }

    fun increaseAutoPageTurnSpeed() {
        updateAutoPageTurnInterval(_state.value.autoPageTurnIntervalMs - AutoPageTurnSpeedConfig.STEP_INTERVAL_MS)
    }

    fun decreaseAutoPageTurnSpeed() {
        updateAutoPageTurnInterval(_state.value.autoPageTurnIntervalMs + AutoPageTurnSpeedConfig.STEP_INTERVAL_MS)
    }

    private fun updateAutoPageTurnInterval(intervalMs: Long) {
        val normalizedIntervalMs = AutoPageTurnSpeedConfig.normalize(intervalMs)
        if (normalizedIntervalMs == _state.value.autoPageTurnIntervalMs) {
            return
        }

        prefs.edit()
            .putString(AppConfig.KEY_READER_AUTO_TURN_SPEED, AutoPageTurnSpeedConfig.toStorage(normalizedIntervalMs))
            .apply()

        _state.update {
            it.copy(
                autoPageTurnIntervalMs = normalizedIntervalMs,
                lastSyncMessage = "自动翻页速度：${AutoPageTurnSpeedConfig.formatLabel(normalizedIntervalMs)}",
            )
        }
    }

    fun pauseAutoPageTurn(reason: String? = null) {
        _state.update {
            if (!it.autoPageTurnEnabled) {
                it
            } else {
                it.copy(
                    autoPageTurnEnabled = false,
                    lastSyncMessage = reason ?: "自动翻页已暂停",
                )
            }
        }
    }

    fun cycleReaderFontStyle() {
        val options = _state.value.readerFonts.filter { !it.fromServer || it.downloaded }
        if (options.isEmpty()) {
            return
        }
        val currentKey = _state.value.readerFontKey
        val currentIndex = options.indexOfFirst { it.key == currentKey }.let { if (it < 0) 0 else it }
        val next = options[(currentIndex + 1) % options.size]
        applyReaderFont(next.key)
    }

    fun increaseReaderFontSize() {
        updateReaderFontSize(_state.value.readerFontSizeSp + 2)
    }

    fun decreaseReaderFontSize() {
        updateReaderFontSize(_state.value.readerFontSizeSp - 2)
    }

    fun increaseReaderLineSpacing() {
        updateReaderLineSpacing(_state.value.readerLineSpacing + 0.1f)
    }

    fun decreaseReaderLineSpacing() {
        updateReaderLineSpacing(_state.value.readerLineSpacing - 0.1f)
    }

    fun syncCurrentProgress(force: Boolean = false) {
        val snapshot = _state.value
        val payload = buildProgressPayload(snapshot) ?: return
        if (!refreshNetworkAvailability()) {
            enqueuePendingProgress(payload, if (force) "WiFi 未连接，进度已加入待补传" else "离线状态，进度已暂存")
            return
        }
        if (!force) {
            val now = System.currentTimeMillis()
            if (now - lastProgressSyncAtMs < progressSyncCooldownMs) {
                return
            }
            lastProgressSyncAtMs = now
        }

        viewModelScope.launch {
            runCatching { repository.upsertSyncProgress(payload) }
                .onSuccess { item ->
                    if (handleSyncUpsertResponse(payload, item, "当前进度同步")) {
                        flushPendingSyncQueue("当前进度同步成功，开始补传")
                    }
                }
                .onFailure {
                    enqueuePendingProgress(payload, "同步失败，进度已加入待补传")
                }
        }
    }

    fun pullRemoteProgress() {
        val snapshot = _state.value
        if (snapshot.userId.isBlank()) {
            return
        }
        flushPendingSyncQueue("拉取云端进度前补传")
        runRequest(
            block = { repository.pullSyncProgress(snapshot.userId, snapshot.syncCursor, limit = 100) },
            onSuccess = { response ->
                val remoteChapterMap = response.items.associate { item ->
                    resolveBookKey(item.bookKey, item.sourceUrl, item.bookUrl) to (item.chapterIdx + 1).coerceAtLeast(1)
                }
                val remotePositionMap = response.items.associate { item ->
                    resolveBookKey(item.bookKey, item.sourceUrl, item.bookUrl) to normalizeReadingPosition(item.position)
                }
                _state.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = null,
                        syncCursor = response.nextCursor,
                        lastSyncRevision = response.nextCursor,
                        remoteReadingChapterByBook = it.remoteReadingChapterByBook + remoteChapterMap,
                        remoteReadingPositionByBook = it.remoteReadingPositionByBook + remotePositionMap,
                        lastSyncMessage = "已拉取 ${response.items.size} 条云端进度",
                    )
                }

                val activeBookKey = _state.value.activeBookKey
                val match = response.items.lastOrNull {
                    resolveBookKey(it.bookKey, it.sourceUrl, it.bookUrl) == activeBookKey
                }
                if (match != null && _state.value.chapters.isNotEmpty()) {
                    val targetListIndex = _state.value.chapters.indexOfFirst { chapter ->
                        chapter.idx == match.chapterIdx
                    }.let { if (it < 0) 0 else it }
                    viewModelScope.launch {
                        loadChapterInternal(
                            targetListIndex,
                            pushProgress = false,
                            restorePosition = match.position,
                        )
                    }
                }
            },
            onErrorPrefix = "拉取云端进度失败",
        )
    }

    fun pullServerBookshelfNow() {
        refreshServerBooks(showLoading = true)
    }

    fun syncOnAppForeground() {
        refreshLocalBookshelf(showLoading = false)
        refreshCacheStatsDeferred(delayMs = 2_000L)
        wifiMonitor.refresh()
        if (networkGate.canUseNetwork()) {
            flushPendingSyncQueue("应用回前台，尝试补传进度")
            scheduleWifiFullSync("应用回到前台")
        }
    }

    fun onFirstScreenDisplayed(elapsedSinceLaunchMs: Long) {
        if (startupFirstScreenDisplayed) {
            return
        }

        startupFirstScreenDisplayed = true
        val firstScreenElapsedMs = elapsedSinceLaunchMs.coerceAtLeast(0L)
        val startupCacheDelayMs = (STARTUP_CACHE_STATS_TARGET_MS - firstScreenElapsedMs).coerceAtLeast(0L)

        refreshLocalBookshelfDeferred(delayMs = STARTUP_LOCAL_SHELF_DELAY_MS)
        refreshCacheStatsDeferred(delayMs = startupCacheDelayMs)
        if (networkGate.canUseNetwork()) {
            scheduleWifiFullSync(reason = "首屏完成后启动同步", initialDelayMs = 0L)
        }
    }

    fun syncBeforeExit(onComplete: () -> Unit) {
        persistCurrentReadingProgress()

        val payload = buildProgressPayload(_state.value)
        if (payload == null) {
            onComplete()
            return
        }

        if (!networkGate.canUseNetwork()) {
            enqueuePendingProgress(payload, "退出前离线，进度已加入待补传")
            onComplete()
            return
        }

        viewModelScope.launch {
            val syncAttempt = withTimeoutOrNull(1_500L) {
                runCatching { repository.upsertSyncProgress(payload) }
            }

            when {
                syncAttempt == null -> {
                    enqueuePendingProgress(payload, "退出前同步超时，进度已加入待补传")
                }

                syncAttempt.isSuccess -> {
                    val item = syncAttempt.getOrNull()
                    if (item != null && handleSyncUpsertResponse(payload, item, "退出前同步")) {
                        flushPendingSyncQueue("退出前同步成功，开始补传")
                    }
                }

                else -> {
                    enqueuePendingProgress(payload, "退出前同步失败，进度已加入待补传")
                }
            }

            onComplete()
        }
    }

    fun syncOnAppBackground(allowNetworkSync: Boolean = true) {
        persistCurrentReadingProgress()
        if (allowNetworkSync) {
            syncCurrentProgress(force = false)
        }
    }

    fun setReaderVisible(visible: Boolean) {
        _state.update {
            it.copy(
                readerVisible = visible,
                pendingReaderCommand = if (visible) it.pendingReaderCommand else ReaderHardwareAction.NONE,
                syncConflictDialogVisible = if (visible) {
                    it.syncConflict != null
                } else {
                    false
                },
            )
        }
    }

    fun handleReaderHardwareKey(keyCode: Int): Boolean {
        if (!_state.value.readerVisible) {
            return false
        }
        val command = when (keyCode) {
            KeyEvent.KEYCODE_DPAD_LEFT,
            KeyEvent.KEYCODE_PAGE_UP,
            KeyEvent.KEYCODE_VOLUME_UP,
            -> ReaderHardwareAction.PREVIOUS_PAGE

            KeyEvent.KEYCODE_DPAD_RIGHT,
            KeyEvent.KEYCODE_PAGE_DOWN,
            KeyEvent.KEYCODE_VOLUME_DOWN,
            -> ReaderHardwareAction.NEXT_PAGE

            else -> ReaderHardwareAction.NONE
        }
        if (command == ReaderHardwareAction.NONE) {
            return false
        }
        _state.update {
            it.copy(
                pendingReaderCommand = command,
                readerCommandSignal = it.readerCommandSignal + 1,
            )
        }
        return true
    }

    fun updateActiveChapterPosition(position: Double) {
        val bookKey = _state.value.activeBookKey ?: return
        val normalizedChunkPosition = normalizeReadingPosition(position)
        val snapshot = _state.value
        val normalizedGlobalPosition = resolveGlobalChapterPosition(snapshot, normalizedChunkPosition)
        if (kotlin.math.abs(normalizedGlobalPosition - snapshot.activeChapterPosition) < 0.02) {
            return
        }
        _state.update {
            it.copy(
                activeChapterPosition = normalizedGlobalPosition,
                activeChapterScrollPosition = normalizedChunkPosition,
                readingPositionByBook = it.readingPositionByBook + (bookKey to normalizedGlobalPosition),
            )
        }

        maybeSwitchChapterRenderChunk(bookKey)
    }

    fun persistCurrentReadingProgress() {
        persistActiveBookReadingChapter()
    }

    fun refreshActiveBookCache() {
        viewModelScope.launch {
            val activeBook = currentActiveShelfBook()
            if (activeBook == null) {
                _state.update { it.copy(errorMessage = "当前没有可缓存的本地书籍") }
                return@launch
            }
            offlineLocalShelfBookToDevice(activeBook)
        }
    }

    fun resolveSyncConflictUseRemote() {
        val conflict = _state.value.syncConflict ?: return
        applyRemoteProgress(conflict.remote, "已采用云端进度")
    }

    fun forceSyncConflictLocal() {
        val conflict = _state.value.syncConflict ?: return
        viewModelScope.launch {
            runCatching { repository.upsertSyncProgress(conflict.local.copy(force = true)) }
                .onSuccess { item ->
                    if (handleSyncUpsertResponse(conflict.local.copy(force = true), item, "强制覆盖云端进度")) {
                        _state.update {
                            it.copy(lastSyncMessage = "已强制覆盖云端进度 rev=${item.revision}")
                        }
                    }
                }
                .onFailure { error ->
                    _state.update {
                        it.copy(
                            errorMessage = formatError("强制覆盖云端进度失败", error),
                            lastSyncMessage = "强制覆盖云端进度失败",
                        )
                    }
                }
        }
    }

    fun clearClientCache() {
        runRequest(
            block = {
                repository.clearLocalCache()
                repository.getClientCacheStats()
            },
            onSuccess = { latestClientStats ->
                _state.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = null,
                        localBookshelf = emptyList(),
                        activeBookName = "",
                        activeBookKey = null,
                        activeBookUrl = null,
                        activeSourceUrl = null,
                        chapters = emptyList(),
                        activeChapterListIndex = 0,
                        activeChapterCached = false,
                        activeChapterTitle = "",
                        activeChapterPosition = 0.0,
                        activeChapterScrollPosition = 0.0,
                        chapterRenderChunkIndex = 0,
                        chapterRenderChunkCount = 1,
                        chapterRenderChunkStart = 0,
                        chapterRenderChunkEnd = 0,
                        chapterRenderTotalChars = 0,
                        chapterType = "novel",
                        chapterImages = emptyList(),
                        chapterText = "",
                        readingChapterByBook = emptyMap(),
                        readingPositionByBook = emptyMap(),
                        remoteReadingChapterByBook = emptyMap(),
                        remoteReadingPositionByBook = emptyMap(),
                        localCacheStatusMessage = "本地缓存已清理",
                        lastSyncMessage = "本地缓存已清理",
                        clientCacheStats = latestClientStats,
                        clientCacheMessage = "本地缓存已清理（章节 ${latestClientStats.chapterEntries} 条）",
                        syncConflict = null,
                        syncConflictDialogVisible = false,
                    )
                }
                clearLastActiveReadingSession()
                clearPendingSyncQueue("本地缓存已清理，待补传队列已清空")
            },
            onErrorPrefix = "清理本地缓存失败",
        )
    }

    fun clearError() {
        _state.update { it.copy(errorMessage = null) }
    }

    private fun observeWifiConnectivity() {
        viewModelScope.launch {
            wifiMonitor.isWifiOnline.collect { online ->
                _state.update {
                    it.copy(
                        isNetworkAvailable = online,
                        networkMode = networkModeFor(online),
                    )
                }
                if (online) {
                    if (!startupFirstScreenDisplayed) {
                        _state.update { it.copy(lastSyncMessage = "WiFi 已连接，等待首屏完成后同步") }
                        return@collect
                    }
                    flushPendingSyncQueue("WiFi 恢复，开始补传待同步进度")
                    scheduleWifiFullSync("WiFi 已连接")
                    viewModelScope.launch {
                        currentActiveShelfBook()?.let { shelfBook ->
                            startBackgroundBookCache(shelfBook, "WiFi 恢复后继续后台缓存")
                        }
                    }
                } else {
                    wifiFullSyncJob?.cancel()
                    backgroundBookCacheJob?.cancel()
                    backgroundBookCacheJob = null
                    backgroundBookCacheBookKey = null
                    offlineDownloadManager.cancel()
                    repository.cancelNetworkRequests()
                    _state.update {
                        it.copy(
                            offlineDownloadActive = false,
                            isLoading = false,
                            lastSyncMessage = "WiFi 已关闭，已停止所有联网任务",
                            localCacheStatusMessage = if (it.offlineDownloadActive) "WiFi 已关闭，离线缓存已暂停" else it.localCacheStatusMessage,
                        )
                    }
                }
            }
        }
    }

    private fun scheduleWifiFullSync(reason: String, initialDelayMs: Long = 3_000L) {
        wifiFullSyncJob?.cancel()
        wifiFullSyncJob = viewModelScope.launch {
            if (initialDelayMs > 0L) {
                delay(initialDelayMs)
            }
            if (!networkGate.canUseNetwork()) {
                _state.update { it.copy(lastSyncMessage = "WiFi 已断开，跳过全量同步") }
                return@launch
            }
            runLightweightProgressSync(reason)
        }
    }

    private fun runLightweightProgressSync(reason: String) {
        runRequest(
            block = { performLightweightProgressSync(reason) },
            onSuccess = { result ->
                _state.update { state ->
                    state.copy(
                        isLoading = false,
                        errorMessage = null,
                        remoteReadingChapterByBook = state.remoteReadingChapterByBook + result.remoteChapterMap,
                        remoteReadingPositionByBook = state.remoteReadingPositionByBook + result.remotePositionMap,
                        syncCursor = maxOf(state.syncCursor, result.nextCursor),
                        lastSyncRevision = maxOf(state.lastSyncRevision, result.progressRevision, result.nextCursor),
                        pendingSyncCount = pendingSyncQueue.size,
                        syncConflict = result.syncConflict ?: state.syncConflict,
                        syncConflictDialogVisible = (result.syncConflict != null && state.readerVisible) ||
                            (state.syncConflict != null && state.syncConflictDialogVisible),
                        lastSyncMessage = result.syncDecisionMessage?.let { message ->
                            "${result.reason}：$message"
                        } ?: "${result.reason}：轻量进度同步完成",
                    )
                }
                flushPendingSyncQueue("轻量进度同步完成后补传待同步进度")
                runFullSync(result.reason)
            },
            onErrorPrefix = "轻量进度同步失败",
            showLoading = false,
        )
    }

    private suspend fun performLightweightProgressSync(reason: String): ProgressSyncResult {
        networkGate.requireWifiOnline("轻量进度同步")
        val snapshot = _state.value

        val syncDecision = buildProgressPayload(snapshot)?.let { payload ->
            runCatching { repository.upsertSyncProgress(payload) }.getOrNull()?.let { item ->
                resolveSyncDecision(payload, item)
            }
        }

        val progressRevision = syncDecision?.remote?.revision ?: snapshot.lastSyncRevision

        val pulled = if (snapshot.userId.isNotBlank()) {
            repository.pullSyncProgress(snapshot.userId, since = snapshot.syncCursor, limit = 120)
        } else {
            null
        }
        val remoteItems = pulled?.items.orEmpty()
        val remoteChapterMap = remoteItems.associate { item ->
            resolveBookKey(item.bookKey, item.sourceUrl, item.bookUrl) to (item.chapterIdx + 1).coerceAtLeast(1)
        }
        val remotePositionMap = remoteItems.associate { item ->
            resolveBookKey(item.bookKey, item.sourceUrl, item.bookUrl) to normalizeReadingPosition(item.position)
        }

        return ProgressSyncResult(
            reason = reason,
            remoteChapterMap = remoteChapterMap,
            remotePositionMap = remotePositionMap,
            nextCursor = pulled?.nextCursor ?: snapshot.syncCursor,
            progressRevision = maxOf(progressRevision, pulled?.nextCursor ?: snapshot.syncCursor),
            syncConflict = syncDecision?.takeIf { it.requiresChoice }?.conflict,
            syncDecisionMessage = syncDecision?.message,
        )
    }

    private fun runFullSync(reason: String) {
        runRequest(
            block = { performFullSync(reason) },
            onSuccess = { result ->
                _state.update { state ->
                    val selected = if (state.selectedCategory == "all") {
                        "all"
                    } else if (result.categories.any { it.name == state.selectedCategory }) {
                        state.selectedCategory
                    } else {
                        "all"
                    }
                    state.copy(
                        isLoading = false,
                        errorMessage = null,
                        serverBooks = result.books,
                        bookCategories = result.categories,
                        readerFonts = result.readerFonts,
                        serverCacheStats = result.serverCacheStats,
                        clientCacheStats = result.clientCacheStats,
                        selectedCategory = selected,
                        pendingSyncCount = pendingSyncQueue.size,
                        lastSyncMessage = "${result.reason}：后台全量数据刷新完成",
                    )
                }
            },
            onErrorPrefix = "后台全量数据刷新失败",
            showLoading = false,
        )
    }

    private suspend fun performFullSync(reason: String): FullSyncResult {
        networkGate.requireWifiOnline("后台全量数据刷新")

        val serverFonts = repository.getServerFonts()
        val localPaths = repository.listDownloadedFontFiles()
        val books = repository.getBooks()
        val categories = repository.getBookCategories()
        val serverCacheStats = repository.getServerCacheStats()
        val clientCacheStats = repository.getClientCacheStats()

        return FullSyncResult(
            reason = reason,
            books = books,
            categories = categories,
            readerFonts = buildReaderFontOptions(serverFonts, localPaths),
            serverCacheStats = serverCacheStats,
            clientCacheStats = clientCacheStats,
        )
    }

    private suspend fun loadChapterIndexForOpen(
        bookKey: String,
        bookUrl: String,
        sourceUrl: String,
        bookName: String,
    ): ChapterIndexLoadResult {
        val localChapters = repository.getLocalChapterIndex(bookKey).sortedBy { it.idx }
        if (localChapters.isNotEmpty()) {
            return ChapterIndexLoadResult(chapters = localChapters, loadedFromNetwork = false)
        }

        if (!repository.canUseNetwork()) {
            return ChapterIndexLoadResult(chapters = emptyList(), loadedFromNetwork = false)
        }

        val shelfBook = repository.ensureLocalShelfBook(
            SearchResultItem(
                bookKey = bookKey,
                name = bookName,
                bookUrl = bookUrl,
                sourceUrl = sourceUrl,
            )
        )
        val remoteChapters = repository.fetchRemoteChapterIndex(shelfBook).sortedBy { it.idx }
        return ChapterIndexLoadResult(chapters = remoteChapters, loadedFromNetwork = true)
    }

    private fun startBackgroundBookCache(book: LocalShelfBook, reason: String) {
        if (_state.value.offlineDownloadActive) {
            return
        }
        if (!repository.canUseNetwork()) {
            return
        }
        if (backgroundBookCacheJob?.isActive == true && backgroundBookCacheBookKey == book.bookKey) {
            return
        }

        backgroundBookCacheJob?.cancel()
        backgroundBookCacheBookKey = book.bookKey

        _state.update {
            it.copy(localCacheStatusMessage = "${book.name}: 已进入阅读，后台缓存进行中")
        }

        backgroundBookCacheJob = viewModelScope.launch {
            runCatching {
                repository.cacheBookToLocal(book) { cached, total, failed ->
                    _state.update { state ->
                        state.copy(
                            localCacheStatusMessage = "${book.name}: 后台缓存 $cached/$total，失败 $failed",
                        )
                    }
                }
            }.onSuccess { summary ->
                _state.update {
                    it.copy(
                        localCacheStatusMessage = "${book.name}: 后台缓存完成 ${summary.cached}/${summary.total}，失败 ${summary.failed}",
                        lastSyncMessage = reason,
                    )
                }
                refreshLocalBookshelf(showLoading = false)
                refreshCacheStats(showLoading = false)
            }.onFailure { error ->
                when (error) {
                    is CancellationException -> Unit
                    is NetworkDisabledException -> {
                        _state.update {
                            it.copy(localCacheStatusMessage = "${book.name}: WiFi 已关闭，后台缓存暂停")
                        }
                    }

                    else -> {
                        _state.update {
                            it.copy(localCacheStatusMessage = "${book.name}: 后台缓存失败：${error.message ?: "未知错误"}")
                        }
                    }
                }
            }

            if (backgroundBookCacheBookKey == book.bookKey) {
                backgroundBookCacheBookKey = null
            }
            backgroundBookCacheJob = null
        }
    }

    private fun openBook(
        bookKey: String,
        bookUrl: String,
        sourceUrl: String,
        bookName: String,
        preferredChapterNumber: Int,
        preferredPosition: Double = 0.0,
    ) {
        runRequest(
            block = {
                val chapterIndex = loadChapterIndexForOpen(
                    bookKey = bookKey,
                    bookUrl = bookUrl,
                    sourceUrl = sourceUrl,
                    bookName = bookName,
                )
                val openProgress = resolveOpenProgressPreference(
                    bookKey = bookKey,
                    preferredChapterNumber = preferredChapterNumber,
                    preferredPosition = preferredPosition,
                )
                chapterIndex to openProgress
            },
            onSuccess = { (chapterIndex, openProgress) ->
                if (chapterIndex.chapters.isEmpty()) {
                    _state.update {
                        it.copy(
                            isLoading = false,
                            errorMessage = "本书尚未缓存章节，请开启 WiFi 后先缓存到本地",
                            activeBookName = bookName,
                            activeBookKey = bookKey,
                            activeBookUrl = bookUrl,
                            activeSourceUrl = sourceUrl,
                            chapters = emptyList(),
                            activeChapterListIndex = 0,
                            activeChapterCached = false,
                            activeChapterTitle = "",
                            activeChapterPosition = 0.0,
                            activeChapterScrollPosition = 0.0,
                            chapterRenderChunkIndex = 0,
                            chapterRenderChunkCount = 1,
                            chapterRenderChunkStart = 0,
                            chapterRenderChunkEnd = 0,
                            chapterRenderTotalChars = 0,
                            chapterText = "本书暂无章节目录。请连接 WiFi 后重试，客户端会先进入阅读再后台缓存。",
                            autoPageTurnEnabled = false,
                        )
                    }
                    persistLastActiveReadingSession(
                        bookKey = bookKey,
                        bookName = bookName,
                        bookUrl = bookUrl,
                        sourceUrl = sourceUrl,
                        chapterNumber = openProgress.chapterNumber,
                        position = openProgress.position,
                    )
                    return@runRequest
                }

                val preferredIndex = (openProgress.chapterNumber - 1).coerceIn(0, chapterIndex.chapters.lastIndex)
                val resolvedChapterNumber = preferredIndex + 1
                val resolvedPosition = normalizeReadingPosition(openProgress.position)
                _state.update {
                    val remoteItem = openProgress.remoteItem
                    val remoteBookKey = if (remoteItem != null) {
                        resolveBookKey(remoteItem.bookKey, remoteItem.sourceUrl, remoteItem.bookUrl)
                    } else {
                        null
                    }
                    it.copy(
                        isLoading = false,
                        errorMessage = null,
                        activeBookName = bookName,
                        activeBookKey = bookKey,
                        activeBookUrl = bookUrl,
                        activeSourceUrl = sourceUrl,
                        chapters = chapterIndex.chapters,
                        activeChapterListIndex = preferredIndex,
                        activeChapterCached = chapterIndex.chapters[preferredIndex].isCached,
                        activeChapterPosition = resolvedPosition,
                        activeChapterScrollPosition = resolvedPosition,
                        readingChapterByBook = it.readingChapterByBook + (bookKey to resolvedChapterNumber),
                        readingPositionByBook = it.readingPositionByBook + (bookKey to resolvedPosition),
                        remoteReadingChapterByBook = if (remoteItem != null && remoteBookKey != null) {
                            it.remoteReadingChapterByBook + (
                                remoteBookKey to (remoteItem.chapterIdx + 1).coerceAtLeast(1)
                            )
                        } else {
                            it.remoteReadingChapterByBook
                        },
                        remoteReadingPositionByBook = if (remoteItem != null && remoteBookKey != null) {
                            it.remoteReadingPositionByBook + (
                                remoteBookKey to normalizeReadingPosition(remoteItem.position)
                            )
                        } else {
                            it.remoteReadingPositionByBook
                        },
                        syncCursor = maxOf(it.syncCursor, openProgress.pulledCursor ?: it.syncCursor),
                        lastSyncRevision = maxOf(it.lastSyncRevision, openProgress.pulledCursor ?: it.lastSyncRevision),
                        chapterRenderChunkIndex = 0,
                        chapterRenderChunkCount = 1,
                        chapterRenderChunkStart = 0,
                        chapterRenderChunkEnd = 0,
                        chapterRenderTotalChars = 0,
                        lastSyncMessage = if (openProgress.adoptedRemote) {
                            "检测到云端进度，已自动跳转到第 $resolvedChapterNumber 章"
                        } else {
                            it.lastSyncMessage
                        },
                    )
                }
                persistLastActiveReadingSession(
                    bookKey = bookKey,
                    bookName = bookName,
                    bookUrl = bookUrl,
                    sourceUrl = sourceUrl,
                    chapterNumber = resolvedChapterNumber,
                    position = resolvedPosition,
                )
                viewModelScope.launch {
                    if (openProgress.adoptedRemote) {
                        runCatching {
                            repository.updateLocalReadProgress(bookKey, resolvedChapterNumber, resolvedPosition)
                        }
                    }
                    currentActiveShelfBook()?.let { shelfBook ->
                        runCatching { repository.seedLocalChapterIndex(shelfBook, chapterIndex.chapters) }
                    }
                    loadChapterInternal(
                        preferredIndex,
                        pushProgress = false,
                        restorePosition = resolvedPosition,
                    )

                    currentActiveShelfBook()?.let { shelfBook ->
                        if (chapterIndex.loadedFromNetwork || chapterIndex.chapters.any { !it.isCached }) {
                            startBackgroundBookCache(
                                book = shelfBook,
                                reason = "已进入阅读，后台缓存已完成",
                            )
                        }
                    }
                }
            },
            onErrorPrefix = "打开书籍失败",
        )
    }

    private suspend fun resolveOpenProgressPreference(
        bookKey: String,
        preferredChapterNumber: Int,
        preferredPosition: Double,
    ): OpenProgressDecision {
        val normalizedLocalPosition = normalizeReadingPosition(preferredPosition)
        val normalizedLocalChapter = preferredChapterNumber.coerceAtLeast(1)
        if (!isInitialLocalProgress(normalizedLocalChapter, normalizedLocalPosition)) {
            return OpenProgressDecision(
                chapterNumber = normalizedLocalChapter,
                position = normalizedLocalPosition,
                adoptedRemote = false,
                remoteItem = null,
                pulledCursor = null,
            )
        }

        val snapshot = _state.value
        val localFallback = OpenProgressDecision(
            chapterNumber = normalizedLocalChapter,
            position = normalizedLocalPosition,
            adoptedRemote = false,
            remoteItem = null,
            pulledCursor = null,
        )

        if (snapshot.userId.isNotBlank() && repository.canUseNetwork()) {
            val pulled = runCatching {
                repository.pullSyncProgress(snapshot.userId, since = 0, limit = 200)
            }.getOrNull()
            if (pulled != null) {
                val remoteItem = pulled.items.lastOrNull { item ->
                    resolveBookKey(item.bookKey, item.sourceUrl, item.bookUrl) == bookKey
                }
                if (remoteItem != null) {
                    val remoteChapter = (remoteItem.chapterIdx + 1).coerceAtLeast(1)
                    val remotePosition = normalizeReadingPosition(remoteItem.position)
                    if (isAdvancedProgress(remoteChapter, remotePosition)) {
                        return OpenProgressDecision(
                            chapterNumber = remoteChapter,
                            position = remotePosition,
                            adoptedRemote = true,
                            remoteItem = remoteItem,
                            pulledCursor = pulled.nextCursor,
                        )
                    }
                }
            }
        }

        val cachedRemoteChapter = snapshot.remoteReadingChapterByBook[bookKey] ?: 1
        val cachedRemotePosition = normalizeReadingPosition(
            snapshot.remoteReadingPositionByBook[bookKey] ?: 0.0
        )
        if (isAdvancedProgress(cachedRemoteChapter, cachedRemotePosition)) {
            return OpenProgressDecision(
                chapterNumber = cachedRemoteChapter,
                position = cachedRemotePosition,
                adoptedRemote = true,
                remoteItem = null,
                pulledCursor = null,
            )
        }

        return localFallback
    }

    private fun isInitialLocalProgress(chapterNumber: Int, position: Double): Boolean {
        val normalizedChapter = chapterNumber.coerceAtLeast(1)
        val normalizedPosition = normalizeReadingPosition(position)
        return normalizedChapter <= 1 && normalizedPosition <= 0.0001
    }

    private fun isAdvancedProgress(chapterNumber: Int, position: Double): Boolean {
        val normalizedChapter = chapterNumber.coerceAtLeast(1)
        val normalizedPosition = normalizeReadingPosition(position)
        return normalizedChapter > 1 || normalizedPosition > 0.0001
    }

    private suspend fun loadChapterInternal(
        chapterListIndex: Int,
        pushProgress: Boolean,
        restorePosition: Double? = null,
    ) {
        val snapshot = _state.value
        val activeBook = currentActiveShelfBook() ?: return
        val chapter = snapshot.chapters.getOrNull(chapterListIndex) ?: return
        val normalizedRestorePosition = normalizeReadingPosition(
            restorePosition ?: snapshot.readingPositionByBook[activeBook.bookKey] ?: 0.0
        )

        _state.update {
            it.copy(
                isLoading = true,
                errorMessage = null,
            )
        }

        runCatching {
            var chapterContent = repository.getCachedChapterContent(activeBook.bookKey, chapter.idx)
            var loadedFromNetwork = false

            if (chapterContent == null && repository.canUseNetwork()) {
                val remoteContent = repository.getChapterContent(chapter.url, activeBook.sourceUrl)
                repository.saveChapterToLocalCache(
                    book = activeBook,
                    chapter = chapter,
                    content = remoteContent,
                    totalChapters = snapshot.chapters.size.coerceAtLeast(chapterListIndex + 1),
                )
                chapterContent = remoteContent
                loadedFromNetwork = true
            }

            chapterContent to loadedFromNetwork
        }.onSuccess { (content, loadedFromNetwork) ->
            if (content == null) {
                _state.update {
                    it.copy(
                        isLoading = false,
                        activeChapterListIndex = chapterListIndex,
                        activeChapterCached = false,
                        activeChapterTitle = chapter.title,
                        chapters = it.chapters.mapIndexed { index, chapterItem ->
                            if (index == chapterListIndex) chapterItem.copy(isCached = false) else chapterItem
                        },
                        chapterType = "novel",
                        chapterImages = emptyList(),
                        activeChapterPosition = 0.0,
                        activeChapterScrollPosition = 0.0,
                        chapterRenderChunkIndex = 0,
                        chapterRenderChunkCount = 1,
                        chapterRenderChunkStart = 0,
                        chapterRenderChunkEnd = 0,
                        chapterRenderTotalChars = 0,
                        chapterRestoreToken = it.chapterRestoreToken + 1,
                        chapterText = "本章未缓存。WiFi 关闭时不会自动联网；请在书架中选择更新本地缓存。",
                        localCacheStatusMessage = "${activeBook.name}: 第 ${chapter.idx + 1} 章未缓存",
                    )
                }
                persistActiveBookReadingChapter()
                refreshPolicy.resetChapter()
                applyRefreshAction(RefreshAction.FULL)
                return@onSuccess
            }

            val cacheSummary = repository.getLocalCacheSummary(activeBook.bookKey)
            val cacheMessage = if (loadedFromNetwork) {
                "${activeBook.name}: 已加载第 ${chapter.idx + 1} 章，后台继续缓存 ${cacheSummary.cached}/${cacheSummary.total}"
            } else {
                "本地缓存 ${cacheSummary.cached}/${cacheSummary.total}"
            }

            if (content.type == "manga") {
                _state.update {
                    it.copy(
                        isLoading = false,
                        activeChapterListIndex = chapterListIndex,
                        activeChapterCached = true,
                        activeChapterTitle = chapter.title,
                        chapters = it.chapters.mapIndexed { index, chapterItem ->
                            if (index == chapterListIndex) chapterItem.copy(isCached = true) else chapterItem
                        },
                        activeChapterPosition = normalizedRestorePosition,
                        activeChapterScrollPosition = normalizeReadingPosition(normalizedRestorePosition),
                        chapterRenderChunkIndex = 0,
                        chapterRenderChunkCount = 1,
                        chapterRenderChunkStart = 0,
                        chapterRenderChunkEnd = 0,
                        chapterRenderTotalChars = 0,
                        chapterRestoreToken = it.chapterRestoreToken + 1,
                        chapterType = "manga",
                        chapterImages = content.images,
                        chapterText = buildMangaPlaceholder(content.images),
                        localCacheStatusMessage = cacheMessage,
                    )
                }
            } else {
                val chunk = computeChunkState(content.content, normalizedRestorePosition)
                _state.update {
                    it.copy(
                        isLoading = false,
                        activeChapterListIndex = chapterListIndex,
                        activeChapterCached = true,
                        activeChapterTitle = chapter.title,
                        chapters = it.chapters.mapIndexed { index, chapterItem ->
                            if (index == chapterListIndex) chapterItem.copy(isCached = true) else chapterItem
                        },
                        activeChapterPosition = normalizedRestorePosition,
                        activeChapterScrollPosition = chunk.chunkPosition,
                        chapterRenderChunkIndex = chunk.chunkIndex,
                        chapterRenderChunkCount = chunk.chunkCount,
                        chapterRenderChunkStart = chunk.chunkStart,
                        chapterRenderChunkEnd = chunk.chunkEnd,
                        chapterRenderTotalChars = chunk.totalChars,
                        chapterRestoreToken = it.chapterRestoreToken + 1,
                        chapterType = "novel",
                        chapterImages = emptyList(),
                        chapterText = chunk.chunkText,
                        localCacheStatusMessage = cacheMessage,
                    )
                }
            }

            persistActiveBookReadingChapter()
            refreshPolicy.resetChapter()
            applyRefreshAction(RefreshAction.FULL)
            refreshLocalBookshelf(showLoading = false)
            if (loadedFromNetwork) {
                startBackgroundBookCache(
                    book = activeBook,
                    reason = "按需加载后，后台缓存已完成",
                )
            }
            if (pushProgress) {
                syncCurrentProgress(force = false)
            }
        }.onFailure { error ->
            _state.update {
                it.copy(
                    isLoading = false,
                    errorMessage = "加载章节失败：${error.message ?: "未知错误"}",
                )
            }
        }
    }

    private fun runOfflinePipeline(
        prepareBook: suspend () -> LocalShelfBook,
        createServerTask: suspend (LocalShelfBook) -> OfflineTaskItem,
        operationLabel: String,
    ) {
        if (!refreshNetworkAvailability()) {
            _state.update { it.copy(lastSyncMessage = "WiFi 未连接，已阻止 $operationLabel") }
            return
        }
        backgroundBookCacheJob?.cancel()
        backgroundBookCacheJob = null
        backgroundBookCacheBookKey = null
        serverOfflineTaskMonitorJob?.cancel()
        _state.update {
            it.copy(
                offlineDownloadActive = true,
                isLoading = true,
                errorMessage = null,
                activeOfflineTask = null,
                activeLocalCache = null,
                localCacheStatusMessage = "$operationLabel 已开始",
                offlineTaskStatusMessage = "$operationLabel：等待服务器任务创建",
            )
        }

        offlineDownloadManager.start(
            scope = viewModelScope,
            prepareBook = prepareBook,
            createServerTask = createServerTask,
            onServerTaskUpdate = { book, task ->
                _state.update {
                    it.copy(
                        activeOfflineTask = ActiveOfflineTaskState(
                            taskId = task.taskId,
                            bookName = book.name,
                            status = task.status,
                            progress = task.progress,
                            cachedChapters = task.cachedChapters,
                            totalChapters = task.totalChapters,
                            errorMessage = task.errorMessage,
                        ),
                        offlineTaskStatusMessage = "${book.name}: 服务器 ${task.status} ${task.progress}% (${task.cachedChapters}/${task.totalChapters})",
                    )
                }
            },
            onLocalProgress = { book, cached, total, failed ->
                _state.update {
                    it.copy(
                        activeLocalCache = ActiveLocalCacheState(
                            bookName = book.name,
                            cachedChapters = cached,
                            totalChapters = total,
                            failedChapters = failed,
                        ),
                        localCacheStatusMessage = "${book.name}: 本地 $cached/$total，失败 $failed",
                    )
                }
            },
            onComplete = { result -> handleOfflineDownloadComplete(result) },
            onError = { error -> handleOfflineDownloadError(operationLabel, error) },
        )
    }

    private suspend fun handleOfflineDownloadComplete(result: OfflineDownloadResult) {
        _state.update {
            it.copy(
                offlineDownloadActive = false,
                isLoading = false,
                errorMessage = null,
                activeOfflineTask = ActiveOfflineTaskState(
                    taskId = result.serverTask.taskId,
                    bookName = result.shelfBook.name,
                    status = result.serverTask.status,
                    progress = result.serverTask.progress,
                    cachedChapters = result.serverTask.cachedChapters,
                    totalChapters = result.serverTask.totalChapters,
                    errorMessage = result.serverTask.errorMessage,
                ),
                activeLocalCache = ActiveLocalCacheState(
                    bookName = result.shelfBook.name,
                    cachedChapters = result.localSummary.cached,
                    totalChapters = result.localSummary.total,
                    failedChapters = result.localSummary.failed,
                ),
                offlineTaskStatusMessage = "${result.shelfBook.name}: 服务器任务 ${result.serverTask.status}",
                localCacheStatusMessage = "${result.shelfBook.name}: 服务器 ${result.serverTask.status}，本地 ${result.localSummary.cached}/${result.localSummary.total}，失败 ${result.localSummary.failed}",
                lastSyncMessage = "已完成本地缓存：${result.shelfBook.name}",
            )
        }
        refreshServerBooks(showLoading = false)
        refreshLocalBookshelf(showLoading = false)
        refreshCacheStats(showLoading = false)
    }

    private suspend fun handleOfflineDownloadError(operationLabel: String, error: Throwable) {
        val message = when (error) {
            is CancellationException -> "$operationLabel 已取消，已完成章节保留"
            is NetworkDisabledException -> "WiFi 已关闭，$operationLabel 已停止，已完成章节保留"
            else -> "$operationLabel 失败：${error.message ?: "未知错误"}"
        }
        _state.update {
            it.copy(
                offlineDownloadActive = false,
                isLoading = false,
                errorMessage = if (error is CancellationException) null else message,
                activeLocalCache = null,
                offlineTaskStatusMessage = message,
                localCacheStatusMessage = message,
            )
        }
        refreshLocalBookshelf(showLoading = false)
        refreshCacheStats(showLoading = false)
    }

    private fun getUserAndDevice(): Pair<String, String>? {
        val snapshot = _state.value
        if (snapshot.userId.isBlank() || snapshot.deviceId.isBlank()) {
            _state.update { it.copy(errorMessage = "缺少用户 ID 或设备 ID") }
            return null
        }
        return snapshot.userId to snapshot.deviceId
    }

    private suspend fun currentActiveShelfBook(): LocalShelfBook? {
        val snapshot = _state.value
        val bookKey = snapshot.activeBookKey ?: return null
        val bookUrl = snapshot.activeBookUrl.orEmpty()
        val sourceUrl = snapshot.activeSourceUrl.orEmpty()

        snapshot.localBookshelf.firstOrNull {
            it.bookKey == bookKey
        }?.let { return it }

        val latestBooks = repository.getLocalBookshelf()
        latestBooks.firstOrNull {
            it.bookKey == bookKey
        }?.let { refreshed ->
            _state.update { it.copy(localBookshelf = latestBooks) }
            return refreshed
        }

        return repository.ensureLocalShelfBook(
            SearchResultItem(
                bookKey = bookKey,
                name = snapshot.activeBookName,
                bookUrl = bookUrl,
                sourceUrl = sourceUrl,
            )
        )
    }

    private fun persistActiveBookReadingChapter() {
        val snapshot = _state.value
        val bookKey = snapshot.activeBookKey ?: return
        val chapterNumber = (snapshot.activeChapterListIndex + 1).coerceAtLeast(1)
        val position = normalizeReadingPosition(snapshot.activeChapterPosition)

        _state.update {
            it.copy(
                readingChapterByBook = it.readingChapterByBook + (bookKey to chapterNumber),
                readingPositionByBook = it.readingPositionByBook + (bookKey to position),
            )
        }

        persistLastActiveReadingSession(
            bookKey = bookKey,
            bookName = snapshot.activeBookName,
            bookUrl = snapshot.activeBookUrl,
            sourceUrl = snapshot.activeSourceUrl,
            chapterNumber = chapterNumber,
            position = position,
        )

        viewModelScope.launch {
            runCatching { repository.updateLocalReadProgress(bookKey, chapterNumber, position) }
        }
    }

    private fun loadLastActiveReadingSession(): LastActiveReadingSession? {
        val bookKey = prefs.getString(AppConfig.KEY_LAST_ACTIVE_BOOK_KEY, null)?.trim().orEmpty()
        val bookUrl = prefs.getString(AppConfig.KEY_LAST_ACTIVE_BOOK_URL, null)?.trim().orEmpty()
        val sourceUrl = prefs.getString(AppConfig.KEY_LAST_ACTIVE_SOURCE_URL, null)?.trim().orEmpty()
        if (bookKey.isBlank() || bookUrl.isBlank() || sourceUrl.isBlank()) {
            return null
        }

        val chapterNumber = prefs.getInt(AppConfig.KEY_LAST_ACTIVE_CHAPTER_NUMBER, 1).coerceAtLeast(1)
        val position = normalizeReadingPosition(
            prefs.getFloat(AppConfig.KEY_LAST_ACTIVE_POSITION, 0f).toDouble(),
        )

        return LastActiveReadingSession(
            bookKey = bookKey,
            bookName = prefs.getString(AppConfig.KEY_LAST_ACTIVE_BOOK_NAME, "")?.trim().orEmpty(),
            bookUrl = bookUrl,
            sourceUrl = sourceUrl,
            chapterNumber = chapterNumber,
            position = position,
        )
    }

    private fun persistLastActiveReadingSession(
        bookKey: String?,
        bookName: String,
        bookUrl: String?,
        sourceUrl: String?,
        chapterNumber: Int,
        position: Double,
    ) {
        if (bookKey.isNullOrBlank() || bookUrl.isNullOrBlank() || sourceUrl.isNullOrBlank()) {
            return
        }

        prefs.edit()
            .putString(AppConfig.KEY_LAST_ACTIVE_BOOK_KEY, bookKey)
            .putString(AppConfig.KEY_LAST_ACTIVE_BOOK_NAME, bookName)
            .putString(AppConfig.KEY_LAST_ACTIVE_BOOK_URL, bookUrl)
            .putString(AppConfig.KEY_LAST_ACTIVE_SOURCE_URL, sourceUrl)
            .putInt(AppConfig.KEY_LAST_ACTIVE_CHAPTER_NUMBER, chapterNumber.coerceAtLeast(1))
            .putFloat(AppConfig.KEY_LAST_ACTIVE_POSITION, normalizeReadingPosition(position).toFloat())
            .apply()
    }

    private fun clearLastActiveReadingSession() {
        prefs.edit()
            .remove(AppConfig.KEY_LAST_ACTIVE_BOOK_KEY)
            .remove(AppConfig.KEY_LAST_ACTIVE_BOOK_NAME)
            .remove(AppConfig.KEY_LAST_ACTIVE_BOOK_URL)
            .remove(AppConfig.KEY_LAST_ACTIVE_SOURCE_URL)
            .remove(AppConfig.KEY_LAST_ACTIVE_CHAPTER_NUMBER)
            .remove(AppConfig.KEY_LAST_ACTIVE_POSITION)
            .apply()
    }

    private fun buildProgressPayload(snapshot: EinkUiState): SyncProgressUpsertRequest? {
        val bookKey = snapshot.activeBookKey ?: return null
        val bookUrl = snapshot.activeBookUrl ?: return null
        val sourceUrl = snapshot.activeSourceUrl ?: return null
        if (snapshot.userId.isBlank() || snapshot.deviceId.isBlank()) {
            return null
        }
        val chapter = snapshot.chapters.getOrNull(snapshot.activeChapterListIndex) ?: return null
        return SyncProgressUpsertRequest(
            userId = snapshot.userId,
            deviceId = snapshot.deviceId,
            bookKey = bookKey,
            bookUrl = bookUrl,
            sourceUrl = sourceUrl,
            bookName = snapshot.activeBookName,
            chapterIdx = chapter.idx,
            chapterTitle = chapter.title,
            chapterUrl = chapter.url,
            position = normalizeReadingPosition(snapshot.activeChapterPosition),
        )
    }

    private fun applySyncedProgress(payload: SyncProgressUpsertRequest, item: SyncProgressItem) {
        val chapterNumber = (payload.chapterIdx + 1).coerceAtLeast(1)
        val normalizedPosition = normalizeReadingPosition(payload.position)
        _state.update {
            it.copy(
                isLoading = false,
                errorMessage = null,
                syncCursor = maxOf(it.syncCursor, item.revision),
                lastSyncRevision = item.revision,
                syncConflict = null,
                syncConflictDialogVisible = false,
                readingChapterByBook = it.readingChapterByBook + (payload.bookKey to chapterNumber),
                readingPositionByBook = it.readingPositionByBook + (payload.bookKey to normalizedPosition),
                remoteReadingChapterByBook = it.remoteReadingChapterByBook + (payload.bookKey to chapterNumber),
                remoteReadingPositionByBook = it.remoteReadingPositionByBook + (payload.bookKey to normalizedPosition),
                lastSyncMessage = "阅读进度已同步 rev=${item.revision}",
            )
        }
    }

    private fun handleSyncUpsertResponse(
        payload: SyncProgressUpsertRequest,
        item: SyncProgressItem,
        trigger: String,
    ): Boolean {
        val decision = resolveSyncDecision(payload, item)

        if (decision.requiresChoice) {
            val conflict = decision.conflict ?: return false
            _state.update {
                it.copy(
                    isLoading = false,
                    errorMessage = null,
                    syncConflict = conflict,
                    syncConflictDialogVisible = it.readerVisible,
                    remoteReadingChapterByBook = it.remoteReadingChapterByBook + (
                        payload.bookKey to (item.chapterIdx + 1).coerceAtLeast(1)
                    ),
                    remoteReadingPositionByBook = it.remoteReadingPositionByBook + (
                        payload.bookKey to normalizeReadingPosition(item.position)
                    ),
                    lastSyncRevision = maxOf(it.lastSyncRevision, item.revision),
                    syncCursor = maxOf(it.syncCursor, item.revision),
                    lastSyncMessage = "$trigger 发生冲突：${decision.message}",
                )
            }
            return false
        }

        when (decision.outcome) {
            SyncDecisionOutcome.ACCEPT_LOCAL -> {
                applySyncedProgress(payload, item)
                _state.update {
                    it.copy(lastSyncMessage = "$trigger：${decision.message}")
                }
            }

            SyncDecisionOutcome.APPLY_REMOTE -> {
                applyRemoteProgress(item, "$trigger：${decision.message}")
            }

            SyncDecisionOutcome.NONE -> {
                if (item.accepted && !item.conflict) {
                    applySyncedProgress(payload, item)
                }
            }
        }
        return true
    }

    private fun resolveSyncDecision(
        payload: SyncProgressUpsertRequest,
        item: SyncProgressItem,
    ): SyncDecision {
        if (item.accepted && !item.conflict) {
            return SyncDecision(
                outcome = SyncDecisionOutcome.ACCEPT_LOCAL,
                requiresChoice = false,
                conflict = null,
                message = "已同步到云端 rev=${item.revision}",
                remote = null,
            )
        }

        val progressGap = calculateProgressGap(payload, item)
        val localAhead = isLocalAhead(payload, item)
        if (progressGap <= progressConflictThreshold) {
            val message = "进度差 ${(progressGap * 100).toInt()}%，已自动采用更靠后进度"
            return if (localAhead) {
                SyncDecision(
                    outcome = SyncDecisionOutcome.ACCEPT_LOCAL,
                    requiresChoice = false,
                    conflict = null,
                    message = message,
                    remote = item,
                )
            } else {
                SyncDecision(
                    outcome = SyncDecisionOutcome.APPLY_REMOTE,
                    requiresChoice = false,
                    conflict = null,
                    message = message,
                    remote = item,
                )
            }
        }

        val summary = "进度差 ${(progressGap * 100).toInt()}%，超过 30%，需手动选择"
        return SyncDecision(
            outcome = SyncDecisionOutcome.NONE,
            requiresChoice = true,
            conflict = buildSyncConflict(payload, item, summary),
            message = summary,
            remote = item,
        )
    }

    private fun calculateProgressGap(
        payload: SyncProgressUpsertRequest,
        remote: SyncProgressItem,
    ): Double {
        val localNormalized = normalizeProgressScalar(payload.chapterIdx, payload.position)
        val remoteNormalized = normalizeProgressScalar(remote.chapterIdx, remote.position)
        return kotlin.math.abs(localNormalized - remoteNormalized)
    }

    private fun normalizeProgressScalar(chapterIdx: Int, position: Double): Double {
        val safeChapter = chapterIdx.coerceAtLeast(0)
        val chapterProgress = safeChapter.toDouble() + normalizeReadingPosition(position)
        return chapterProgress / (chapterProgress + 1.0)
    }

    private fun isLocalAhead(
        payload: SyncProgressUpsertRequest,
        remote: SyncProgressItem,
    ): Boolean {
        return when {
            payload.chapterIdx != remote.chapterIdx -> payload.chapterIdx > remote.chapterIdx
            else -> normalizeReadingPosition(payload.position) >= normalizeReadingPosition(remote.position)
        }
    }

    private fun buildSyncConflict(
        payload: SyncProgressUpsertRequest,
        item: SyncProgressItem,
        summaryOverride: String? = null,
    ): SyncConflictState {
        return SyncConflictState(
            local = payload,
            remote = item,
            summary = summaryOverride ?: describeSyncConflict(item.conflictReason),
        )
    }

    private fun applyRemoteProgress(item: SyncProgressItem, message: String) {
        val bookKey = resolveBookKey(item.bookKey, item.sourceUrl, item.bookUrl)
        val chapterNumber = (item.chapterIdx + 1).coerceAtLeast(1)
        val normalizedPosition = normalizeReadingPosition(item.position)
        _state.update {
            it.copy(
                syncConflict = null,
                syncConflictDialogVisible = false,
                readingChapterByBook = it.readingChapterByBook + (bookKey to chapterNumber),
                readingPositionByBook = it.readingPositionByBook + (bookKey to normalizedPosition),
                remoteReadingChapterByBook = it.remoteReadingChapterByBook + (bookKey to chapterNumber),
                remoteReadingPositionByBook = it.remoteReadingPositionByBook + (bookKey to normalizedPosition),
                syncCursor = maxOf(it.syncCursor, item.revision),
                lastSyncRevision = maxOf(it.lastSyncRevision, item.revision),
                lastSyncMessage = "$message：第 $chapterNumber 章",
            )
        }
        viewModelScope.launch {
            runCatching { repository.updateLocalReadProgress(bookKey, chapterNumber, item.position) }
            if (_state.value.activeBookKey == bookKey && _state.value.chapters.isNotEmpty()) {
                val targetIndex = _state.value.chapters.indexOfFirst { chapter ->
                    chapter.idx == item.chapterIdx
                }.let { if (it < 0) 0 else it }
                loadChapterInternal(targetIndex, pushProgress = false, restorePosition = item.position)
            } else {
                refreshLocalBookshelf(showLoading = false)
            }
        }
    }

    private fun normalizeReadingPosition(position: Double): Double {
        if (!position.isFinite()) {
            return 0.0
        }
        return position.coerceIn(0.0, 1.0)
    }

    private fun resolveGlobalChapterPosition(snapshot: EinkUiState, chunkPosition: Double): Double {
        if (snapshot.chapterType != "novel") {
            return chunkPosition
        }
        val totalChars = snapshot.chapterRenderTotalChars
        val chunkCount = snapshot.chapterRenderChunkCount
        if (totalChars <= 0 || chunkCount <= 1) {
            return chunkPosition
        }
        val chunkSize = chapterChunkSizeChars.toDouble()
        val chunkIndex = snapshot.chapterRenderChunkIndex.coerceIn(0, chunkCount - 1)
        val offset = chunkIndex.toDouble() * chunkSize
        val absolute = offset + (chunkPosition * chunkSize)
        return normalizeReadingPosition(absolute / totalChars.toDouble())
    }

    private fun maybeSwitchChapterRenderChunk(bookKey: String) {
        val snapshot = _state.value
        if (snapshot.chapterType != "novel") {
            return
        }
        if (snapshot.chapterRenderChunkCount <= 1 || snapshot.chapterRenderTotalChars <= chapterChunkSizeChars) {
            return
        }

        val desiredIndex = floor(
            snapshot.activeChapterPosition * snapshot.chapterRenderChunkCount.toDouble()
        ).toInt().coerceIn(0, snapshot.chapterRenderChunkCount - 1)

        if (desiredIndex == snapshot.chapterRenderChunkIndex) {
            return
        }

        val chapterIdx = snapshot.chapters.getOrNull(snapshot.activeChapterListIndex)?.idx ?: return
        val globalPosition = snapshot.activeChapterPosition
        viewModelScope.launch {
            runCatching {
                repository.getCachedChapterContent(bookKey, chapterIdx)
            }.getOrNull()?.takeIf { it.type == "novel" }?.let { content ->
                val chunk = computeChunkState(content.content, globalPosition)
                _state.update { state ->
                    if (state.activeBookKey != bookKey || state.activeChapterListIndex != snapshot.activeChapterListIndex) {
                        return@update state
                    }
                    if (state.chapterType != "novel") {
                        return@update state
                    }
                    state.copy(
                        activeChapterScrollPosition = chunk.chunkPosition,
                        chapterRenderChunkIndex = chunk.chunkIndex,
                        chapterRenderChunkCount = chunk.chunkCount,
                        chapterRenderChunkStart = chunk.chunkStart,
                        chapterRenderChunkEnd = chunk.chunkEnd,
                        chapterRenderTotalChars = chunk.totalChars,
                        chapterRestoreToken = state.chapterRestoreToken + 1,
                        chapterText = chunk.chunkText,
                    )
                }
            }
        }
    }

    private fun computeChunkState(content: String, globalPosition: Double): ChapterRenderChunk {
        val safeText = content.ifBlank { "本章内容为空" }
        val totalChars = safeText.length
        if (totalChars <= chapterChunkSizeChars) {
            return ChapterRenderChunk(
                chunkText = safeText,
                chunkIndex = 0,
                chunkCount = 1,
                chunkStart = 0,
                chunkEnd = totalChars,
                totalChars = totalChars,
                chunkPosition = normalizeReadingPosition(globalPosition),
            )
        }

        val chunkCount = ceil(totalChars.toDouble() / chapterChunkSizeChars.toDouble()).toInt().coerceAtLeast(1)
        val normalizedGlobal = normalizeReadingPosition(globalPosition)
        val chunkIndex = floor(normalizedGlobal * chunkCount.toDouble()).toInt().coerceIn(0, chunkCount - 1)
        val chunkStart = (chunkIndex * chapterChunkSizeChars).coerceIn(0, totalChars)
        val chunkEnd = minOf(chunkStart + chapterChunkSizeChars, totalChars)
        val chunkSpan = (chunkEnd - chunkStart).coerceAtLeast(1)
        val absolutePosition = normalizedGlobal * totalChars.toDouble()
        val chunkPosition = ((absolutePosition - chunkStart.toDouble()) / chunkSpan.toDouble()).coerceIn(0.0, 1.0)

        return ChapterRenderChunk(
            chunkText = safeText.substring(chunkStart, chunkEnd),
            chunkIndex = chunkIndex,
            chunkCount = chunkCount,
            chunkStart = chunkStart,
            chunkEnd = chunkEnd,
            totalChars = totalChars,
            chunkPosition = chunkPosition,
        )
    }

    private data class ChapterRenderChunk(
        val chunkText: String,
        val chunkIndex: Int,
        val chunkCount: Int,
        val chunkStart: Int,
        val chunkEnd: Int,
        val totalChars: Int,
        val chunkPosition: Double,
    )

    private fun clearSyncConflict(message: String? = null) {
        _state.update {
            if (it.syncConflict == null && message == null) {
                it
            } else {
                it.copy(
                    syncConflict = null,
                    syncConflictDialogVisible = false,
                    lastSyncMessage = message ?: it.lastSyncMessage,
                )
            }
        }
    }

    private fun describeSyncConflict(reason: String): String {
        return when (reason) {
            "chapter_regression" -> "云端记录已经在更靠后的章节"
            "position_regression" -> "云端记录在当前章节的位置更靠前"
            else -> if (reason.isBlank()) "云端已存在更新进度" else reason
        }
    }

    private fun refreshNetworkAvailability(): Boolean {
        val available = networkGate.canUseNetwork()
        _state.update {
            it.copy(
                isNetworkAvailable = available,
                networkMode = networkModeFor(available),
            )
        }
        return available
    }

    private fun networkModeFor(available: Boolean): NetworkMode {
        return if (available) NetworkMode.WIFI_ONLINE else NetworkMode.OFFLINE
    }

    private fun resolveBookKey(rawBookKey: String?, sourceUrl: String, bookUrl: String): String {
        return BookIdentity.resolveBookKey(rawBookKey, sourceUrl, bookUrl)
    }

    private fun enqueuePendingProgress(payload: SyncProgressUpsertRequest, message: String) {
        pendingSyncQueue[payload.bookKey] = payload
        savePendingSyncQueue()
        _state.update {
            it.copy(
                pendingSyncCount = pendingSyncQueue.size,
                lastSyncMessage = message,
            )
        }
    }

    private fun flushPendingSyncQueue(trigger: String) {
        if (pendingSyncQueue.isEmpty()) {
            return
        }
        if (!networkGate.canUseNetwork()) {
            refreshNetworkAvailability()
            return
        }

        val entries = pendingSyncQueue.values.toList()
        viewModelScope.launch {
            var successCount = 0
            var conflictCount = 0
            for (payload in entries) {
                val synced = runCatching { repository.upsertSyncProgress(payload) }.getOrNull() ?: continue
                pendingSyncQueue.remove(payload.bookKey)
                if (handleSyncUpsertResponse(payload, synced, "待补传进度")) {
                    successCount += 1
                } else {
                    conflictCount += 1
                }
            }
            savePendingSyncQueue()
            _state.update {
                it.copy(
                    pendingSyncCount = pendingSyncQueue.size,
                    lastSyncMessage = if (successCount > 0) {
                        buildString {
                            append("$trigger：已补传 $successCount 本，剩余 ${pendingSyncQueue.size} 本")
                            if (conflictCount > 0) {
                                append("，冲突 $conflictCount 本")
                            }
                        }
                    } else {
                        buildString {
                            append("$trigger：补传未成功，剩余 ${pendingSyncQueue.size} 本")
                            if (conflictCount > 0) {
                                append("，冲突 $conflictCount 本")
                            }
                        }
                    },
                )
            }
        }
    }

    private fun clearPendingSyncQueue(message: String? = null) {
        if (pendingSyncQueue.isEmpty()) {
            return
        }
        pendingSyncQueue.clear()
        savePendingSyncQueue()
        _state.update {
            it.copy(
                pendingSyncCount = 0,
                lastSyncMessage = message ?: it.lastSyncMessage,
            )
        }
    }

    private fun loadPendingSyncQueue(): LinkedHashMap<String, SyncProgressUpsertRequest> {
        val restored = LinkedHashMap<String, SyncProgressUpsertRequest>()
        val raw = prefs.getString(AppConfig.KEY_PENDING_PROGRESS_QUEUE, null).orEmpty()
        if (raw.isBlank()) {
            return restored
        }

        runCatching {
            val array = JSONArray(raw)
            for (index in 0 until array.length()) {
                val item = array.optJSONObject(index) ?: continue
                val rawBookKey = item.optString("book_key").trim()
                val userId = item.optString("user_id").trim()
                val deviceId = item.optString("device_id").trim()
                val bookUrl = item.optString("book_url").trim()
                val sourceUrl = item.optString("source_url").trim()
                val bookKey = resolveBookKey(rawBookKey, sourceUrl, bookUrl)
                val chapterUrl = item.optString("chapter_url").trim()
                val chapterTitle = item.optString("chapter_title").trim()
                val bookName = item.optString("book_name").trim()
                val chapterIdx = item.optInt("chapter_idx", -1)
                if (
                    bookKey.isBlank() ||
                    userId.isBlank() ||
                    deviceId.isBlank() ||
                    bookUrl.isBlank() ||
                    sourceUrl.isBlank() ||
                    chapterIdx < 0 ||
                    chapterUrl.isBlank() ||
                    chapterTitle.isBlank()
                ) {
                    continue
                }
                restored[bookKey] = SyncProgressUpsertRequest(
                    userId = userId,
                    deviceId = deviceId,
                    bookKey = bookKey,
                    bookUrl = bookUrl,
                    sourceUrl = sourceUrl,
                    bookName = bookName,
                    chapterIdx = chapterIdx,
                    chapterTitle = chapterTitle,
                    chapterUrl = chapterUrl,
                    position = item.optDouble("position", 0.0),
                )
            }
        }

        return restored
    }

    private fun savePendingSyncQueue() {
        val array = JSONArray()
        pendingSyncQueue.values.forEach { payload ->
            array.put(
                JSONObject()
                    .put("user_id", payload.userId)
                    .put("device_id", payload.deviceId)
                    .put("book_key", payload.bookKey)
                    .put("book_url", payload.bookUrl)
                    .put("source_url", payload.sourceUrl)
                    .put("book_name", payload.bookName)
                    .put("chapter_idx", payload.chapterIdx)
                    .put("chapter_title", payload.chapterTitle)
                    .put("chapter_url", payload.chapterUrl)
                    .put("position", payload.position)
            )
        }
        prefs.edit().putString(AppConfig.KEY_PENDING_PROGRESS_QUEUE, array.toString()).apply()
    }

    private fun applyRefreshAction(action: RefreshAction) {
        _state.update {
            it.copy(
                lastRefreshAction = action,
                refreshSignal = it.refreshSignal + 1,
            )
        }
    }

    private fun updateReaderFontSize(targetSizeSp: Int) {
        val normalizedSizeSp = targetSizeSp.coerceIn(18, 36)
        if (normalizedSizeSp == _state.value.readerFontSizeSp) {
            return
        }
        prefs.edit().putInt(AppConfig.KEY_READER_FONT_SIZE, normalizedSizeSp).apply()
        _state.update {
            it.copy(
                readerFontSizeSp = normalizedSizeSp,
                lastSyncMessage = "字号：${normalizedSizeSp}sp",
            )
        }
        applyRefreshAction(RefreshAction.FULL)
    }

    private fun updateReaderLineSpacing(targetLineSpacing: Float) {
        if (!targetLineSpacing.isFinite() || targetLineSpacing <= 0f) {
            return
        }
        val normalizedSpacing = targetLineSpacing
        if (kotlin.math.abs(normalizedSpacing - _state.value.readerLineSpacing) < 0.001f) {
            return
        }
        prefs.edit().putFloat(AppConfig.KEY_READER_LINE_SPACING, normalizedSpacing).apply()
        _state.update {
            it.copy(
                readerLineSpacing = normalizedSpacing,
                lastSyncMessage = "行距：${"%.2f".format(normalizedSpacing)}",
            )
        }
        applyRefreshAction(RefreshAction.FULL)
    }

    private fun buildReaderFontOptions(serverFonts: List<ServerFontItem>, localPaths: List<String>): List<ReaderFontOption> {
        val localPathMap = localPaths.associateBy { path -> path.substringAfterLast('/').lowercase() }
        val remoteOptions = serverFonts.map { font ->
            val localPath = localPathMap[font.fileName.lowercase()]
            ReaderFontOption(
                key = "server:${font.id}",
                name = font.name,
                fromServer = true,
                downloaded = localPath != null,
                filePath = localPath,
                serverMeta = font,
            )
        }

        val remoteFileNames = serverFonts.map { it.fileName.lowercase() }.toSet()
        val localOnlyOptions = localPaths
            .filter { path -> path.substringAfterLast('/').lowercase() !in remoteFileNames }
            .map { path ->
                val filename = path.substringAfterLast('/')
                val fontName = filename.substringBeforeLast('.')
                    .replace(Regex("[_-]"), " ")
                ReaderFontOption(
                    key = "local:$filename",
                    name = fontName,
                    fromServer = false,
                    downloaded = true,
                    filePath = path,
                )
            }

        return builtInFontOptions + remoteOptions + localOnlyOptions
    }

    private fun resolveReaderFontStyle(fontKey: String): ReaderFontStyle {
        if (fontKey == "builtin:sans") {
            return ReaderFontStyle.SANS
        }
        if (fontKey == "builtin:serif") {
            return ReaderFontStyle.SERIF
        }
        val lowered = fontKey.lowercase()
        return if (lowered.contains("sans") || lowered.contains("hei")) ReaderFontStyle.SANS else ReaderFontStyle.SERIF
    }

    private fun buildMangaPlaceholder(images: List<String>): String {
        return buildString {
            appendLine("漫画模式")
            appendLine("当前版本在墨水屏使用图片地址占位显示")
            appendLine("已检测图片 ${images.size} 张")
            images.take(8).forEachIndexed { index, url -> appendLine("${index + 1}. $url") }
        }
    }

    private fun <T> runRequest(
        block: suspend () -> T,
        onSuccess: (T) -> Unit,
        onErrorPrefix: String,
        showLoading: Boolean = true,
    ) {
        _state.update {
            if (showLoading) {
                it.copy(isLoading = true, errorMessage = null)
            } else {
                it.copy(errorMessage = null)
            }
        }
        viewModelScope.launch {
            runCatching { block() }
                .onSuccess { data ->
                    onSuccess(data)
                }
                .onFailure { error ->
                    _state.update {
                        it.copy(
                            isLoading = false,
                            errorMessage = formatError(onErrorPrefix, error),
                        )
                    }
                }
        }
    }

    private fun formatError(prefix: String, error: Throwable): String {
        return when (error) {
            is NetworkDisabledException -> "WiFi 未连接，已阻止联网：${error.operation}"
            is CancellationException -> "操作已取消"
            else -> "$prefix：${error.message ?: "未知错误"}"
        }
    }

    private fun monitorActiveOfflineTask(initialTask: OfflineTaskItem, fallbackBookName: String) {
        serverOfflineTaskMonitorJob?.cancel()
        serverOfflineTaskMonitorJob = viewModelScope.launch {
            try {
                updateActiveOfflineTaskState(initialTask, fallbackBookName)
                val latest = repository.awaitOfflineTask(initialTask.taskId) { task ->
                    updateActiveOfflineTaskState(task, fallbackBookName)
                }
                updateActiveOfflineTaskState(latest, fallbackBookName)
                refreshServerBooks(showLoading = false)
                refreshCacheStats(showLoading = false)
            } catch (error: CancellationException) {
                throw error
            } catch (error: Throwable) {
                val message = formatError("跟踪服务器缓存任务失败", error)
                _state.update {
                    it.copy(
                        errorMessage = message,
                        offlineTaskStatusMessage = message,
                    )
                }
            }
        }
    }

    private fun updateActiveOfflineTaskState(task: OfflineTaskItem, fallbackBookName: String) {
        val resolvedBookName = task.bookName.ifBlank { fallbackBookName }.ifBlank { task.bookKey }
        val statusMessage = buildOfflineTaskStatusMessage(
            bookName = resolvedBookName,
            status = task.status,
            progress = task.progress,
            cachedChapters = task.cachedChapters,
            totalChapters = task.totalChapters,
        )
        _state.update {
            it.copy(
                activeOfflineTask = ActiveOfflineTaskState(
                    taskId = task.taskId,
                    bookName = resolvedBookName,
                    status = task.status,
                    progress = task.progress,
                    cachedChapters = task.cachedChapters,
                    totalChapters = task.totalChapters,
                    errorMessage = task.errorMessage,
                ),
                offlineTaskStatusMessage = statusMessage,
                lastSyncMessage = statusMessage,
            )
        }
    }

    private fun buildOfflineTaskStatusMessage(
        bookName: String,
        status: String,
        progress: Int,
        cachedChapters: Int,
        totalChapters: Int,
    ): String {
        return "$bookName: 服务器 $status $progress% ($cachedChapters/$totalChapters)"
    }

    private data class LastActiveReadingSession(
        val bookKey: String,
        val bookName: String,
        val bookUrl: String,
        val sourceUrl: String,
        val chapterNumber: Int,
        val position: Double,
    )

    private data class ChapterIndexLoadResult(
        val chapters: List<ChapterItem>,
        val loadedFromNetwork: Boolean,
    )

    private data class OpenProgressDecision(
        val chapterNumber: Int,
        val position: Double,
        val adoptedRemote: Boolean,
        val remoteItem: SyncProgressItem?,
        val pulledCursor: Int?,
    )

    private data class ProgressSyncResult(
        val reason: String,
        val remoteChapterMap: Map<String, Int>,
        val remotePositionMap: Map<String, Double>,
        val nextCursor: Int,
        val progressRevision: Int,
        val syncConflict: SyncConflictState?,
        val syncDecisionMessage: String?,
    )

    private data class FullSyncResult(
        val reason: String,
        val books: List<BookItem>,
        val categories: List<BookCategoryItem>,
        val readerFonts: List<ReaderFontOption>,
        val serverCacheStats: ServerCacheStats,
        val clientCacheStats: ClientCacheStats,
    )

    private enum class SyncDecisionOutcome {
        NONE,
        ACCEPT_LOCAL,
        APPLY_REMOTE,
    }

    private data class SyncDecision(
        val outcome: SyncDecisionOutcome,
        val requiresChoice: Boolean,
        val conflict: SyncConflictState?,
        val message: String,
        val remote: SyncProgressItem?,
    )

    companion object {
        private const val STARTUP_CACHE_STATS_TARGET_MS = 9_000L
        private const val STARTUP_LOCAL_SHELF_DELAY_MS = 2_000L

        fun factory(application: Application): ViewModelProvider.Factory {
            return object : ViewModelProvider.Factory {
                override fun <T : androidx.lifecycle.ViewModel> create(
                    modelClass: Class<T>,
                    extras: CreationExtras,
                ): T {
                    @Suppress("UNCHECKED_CAST")
                    return EinkViewModel(application) as T
                }
            }
        }
    }
}