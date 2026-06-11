package com.easyreader.elinkclient.ui

import com.easyreader.elinkclient.core.AppConfig
import com.easyreader.elinkclient.core.EinkRefreshMode
import com.easyreader.elinkclient.core.RefreshAction
import com.easyreader.elinkclient.data.model.BookCategoryItem
import com.easyreader.elinkclient.data.model.BookItem
import com.easyreader.elinkclient.data.model.ChapterItem
import com.easyreader.elinkclient.data.model.ClientCacheStats
import com.easyreader.elinkclient.data.model.LocalShelfBook
import com.easyreader.elinkclient.data.model.OfflineCatalogItem
import com.easyreader.elinkclient.data.model.OfflineTaskItem
import com.easyreader.elinkclient.data.model.SearchResultItem
import com.easyreader.elinkclient.data.model.ServerCacheStats
import com.easyreader.elinkclient.data.model.ServerFontItem
import com.easyreader.elinkclient.data.model.SyncProgressItem
import com.easyreader.elinkclient.data.model.SyncProgressUpsertRequest

enum class ReaderFontStyle {
    SANS,
    SERIF,
}

enum class AutoPageTurnSpeed(val label: String, val intervalMs: Long) {
    SLOW("慢", 7600L),
    MEDIUM("中", 5200L),
    FAST("快", 3200L);

    companion object {
        fun fromStorage(raw: String?): AutoPageTurnSpeed {
            return entries.firstOrNull { it.name == raw } ?: MEDIUM
        }
    }
}

enum class ReaderHardwareAction {
    NONE,
    PREVIOUS_PAGE,
    NEXT_PAGE,
}

data class ReaderFontOption(
    val key: String,
    val name: String,
    val fromServer: Boolean,
    val downloaded: Boolean,
    val filePath: String? = null,
    val serverMeta: ServerFontItem? = null,
)

data class SyncConflictState(
    val local: SyncProgressUpsertRequest,
    val remote: SyncProgressItem,
    val summary: String,
)

data class ActiveOfflineTaskState(
    val taskId: String,
    val bookName: String,
    val status: String,
    val progress: Int,
    val cachedChapters: Int,
    val totalChapters: Int,
    val errorMessage: String = "",
)

data class ActiveLocalCacheState(
    val bookName: String,
    val cachedChapters: Int,
    val totalChapters: Int,
    val failedChapters: Int,
)

data class EinkUiState(
    val baseUrl: String = AppConfig.DEFAULT_BASE_URL,
    val userId: String = AppConfig.DEFAULT_USER_ID,
    val deviceId: String = "",
    val networkMode: NetworkMode = NetworkMode.OFFLINE,
    val syncMode: SyncMode = SyncMode.AUTO_ON_WIFI,
    val isNetworkAvailable: Boolean = false,
    val offlineDownloadActive: Boolean = false,
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val serverBooks: List<BookItem> = emptyList(),
    val localBookshelf: List<LocalShelfBook> = emptyList(),
    val offlineTasks: List<OfflineTaskItem> = emptyList(),
    val offlineCatalog: List<OfflineCatalogItem> = emptyList(),
    val searchKeyword: String = "",
    val searchResults: List<SearchResultItem> = emptyList(),
    val bookCategories: List<BookCategoryItem> = emptyList(),
    val selectedCategory: String = "all",
    val readingChapterByBook: Map<String, Int> = emptyMap(),
    val readingPositionByBook: Map<String, Double> = emptyMap(),
    val remoteReadingChapterByBook: Map<String, Int> = emptyMap(),
    val remoteReadingPositionByBook: Map<String, Double> = emptyMap(),
    val serverCacheStats: ServerCacheStats = ServerCacheStats(books = 0, chapters = 0, bytes = 0),
    val serverCacheMessage: String = "",
    val clientCacheStats: ClientCacheStats = ClientCacheStats(chapterBooks = 0, chapterEntries = 0, fontFiles = 0, bytes = 0),
    val clientCacheMessage: String = "",
    val offlineTaskStatusMessage: String = "",
    val localCacheStatusMessage: String = "",
    val activeBookName: String = "",
    val activeBookKey: String? = null,
    val activeBookUrl: String? = null,
    val activeSourceUrl: String? = null,
    val chapters: List<ChapterItem> = emptyList(),
    val activeChapterListIndex: Int = 0,
    val activeChapterCached: Boolean = false,
    val activeChapterTitle: String = "",
    val activeChapterPosition: Double = 0.0,
    val activeChapterScrollPosition: Double = 0.0,
    val chapterRenderChunkIndex: Int = 0,
    val chapterRenderChunkCount: Int = 1,
    val chapterRenderChunkStart: Int = 0,
    val chapterRenderChunkEnd: Int = 0,
    val chapterRenderTotalChars: Int = 0,
    val chapterRestoreToken: Long = 0L,
    val chapterType: String = "novel",
    val chapterImages: List<String> = emptyList(),
    val chapterText: String = "",
    val readerFontStyle: ReaderFontStyle = ReaderFontStyle.SERIF,
    val readerFontKey: String = "builtin:serif",
    val readerFontPath: String? = null,
    val readerFonts: List<ReaderFontOption> = emptyList(),
    val readerFontSizeSp: Int = 24,
    val readerLineSpacing: Float = 1.85f,
    val autoPageTurnEnabled: Boolean = false,
    val autoPageTurnSpeed: AutoPageTurnSpeed = AutoPageTurnSpeed.MEDIUM,
    val activeOfflineTask: ActiveOfflineTaskState? = null,
    val activeLocalCache: ActiveLocalCacheState? = null,
    val pendingSyncCount: Int = 0,
    val syncConflict: SyncConflictState? = null,
    val syncConflictDialogVisible: Boolean = false,
    val syncCursor: Int = 0,
    val lastSyncRevision: Int = 0,
    val lastSyncMessage: String = "No sync yet",
    val refreshMode: EinkRefreshMode = EinkRefreshMode.BALANCED,
    val refreshEveryTurns: Int = EinkRefreshMode.BALANCED.fullRefreshInterval,
    val readerVisible: Boolean = false,
    val pendingReaderCommand: ReaderHardwareAction = ReaderHardwareAction.NONE,
    val readerCommandSignal: Long = 0L,
    val lastRefreshAction: RefreshAction = RefreshAction.NONE,
    val refreshSignal: Long = 0L,
)
