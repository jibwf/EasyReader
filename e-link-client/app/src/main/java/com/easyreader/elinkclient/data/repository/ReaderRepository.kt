package com.easyreader.elinkclient.data.repository

import android.content.Context
import com.easyreader.elinkclient.core.AppConfig
import com.easyreader.elinkclient.core.BookIdentity
import com.easyreader.elinkclient.core.NetworkGate
import com.easyreader.elinkclient.data.local.LocalCacheStore
import com.easyreader.elinkclient.data.model.BookCreateRequest
import com.easyreader.elinkclient.data.model.BookCategoryAssignRequest
import com.easyreader.elinkclient.data.model.BookCategoryCreateRequest
import com.easyreader.elinkclient.data.model.BookCategoryHiddenRequest
import com.easyreader.elinkclient.data.model.BookCategoryItem
import com.easyreader.elinkclient.data.model.BookCategoryRenameRequest
import com.easyreader.elinkclient.data.model.BookItem
import com.easyreader.elinkclient.data.model.CacheClearRequest
import com.easyreader.elinkclient.data.model.CacheClearResponse
import com.easyreader.elinkclient.data.model.ChapterContent
import com.easyreader.elinkclient.data.model.ChapterItem
import com.easyreader.elinkclient.data.model.ClientCacheStats
import com.easyreader.elinkclient.data.model.LocalCacheSummary
import com.easyreader.elinkclient.data.model.LocalShelfBook
import com.easyreader.elinkclient.data.model.OfflineCatalogItem
import com.easyreader.elinkclient.data.model.OfflineTaskCreateRequest
import com.easyreader.elinkclient.data.model.OfflineTaskItem
import com.easyreader.elinkclient.data.model.SearchResultItem
import com.easyreader.elinkclient.data.model.LoginRequest
import com.easyreader.elinkclient.data.model.LoginResponse
import com.easyreader.elinkclient.data.model.ServerCacheStats
import com.easyreader.elinkclient.data.model.ServerFontItem
import com.easyreader.elinkclient.data.model.SyncProgressItem
import com.easyreader.elinkclient.data.model.SyncProgressUpsertRequest
import com.easyreader.elinkclient.data.model.SyncPullResponse
import com.easyreader.elinkclient.data.network.EasyReaderApi
import com.easyreader.elinkclient.data.network.NetworkModule
import com.squareup.moshi.Types
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.io.File
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import kotlin.LazyThreadSafetyMode

class ReaderRepository(
    context: Context,
    initialBaseUrl: String = AppConfig.DEFAULT_BASE_URL,
    private val networkGate: NetworkGate = NetworkGate(context.applicationContext),
) {
    private val appContext = context.applicationContext
    private val httpClient: OkHttpClient =
        NetworkModule.createHttpClient(appContext, networkGate)
    private val moshi = NetworkModule.createMoshi()
    private val localStore by lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        LocalCacheStore(appContext, moshi)
    }
    private val localFontDir by lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        File(appContext.filesDir, "eink-local-store/fonts")
    }

    private val searchResultListType by lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        Types.newParameterizedType(List::class.java, SearchResultItem::class.java)
    }
    private val searchResultListAdapter by lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        moshi.adapter<List<SearchResultItem>>(searchResultListType)
    }

    @Volatile
    private var normalizedBaseUrl: String = normalizeBaseUrl(initialBaseUrl)

    @Volatile
    private var api: EasyReaderApi =
        NetworkModule.createApi(
            baseUrl = normalizedBaseUrl,
            client = httpClient,
            moshi = moshi,
        )

    fun updateBaseUrl(baseUrl: String) {
        val normalized = normalizeBaseUrl(baseUrl)
        if (normalized == normalizedBaseUrl) {
            return
        }
        normalizedBaseUrl = normalized
        api = NetworkModule.createApi(
            baseUrl = normalized,
            client = httpClient,
            moshi = moshi,
        )
    }

    fun getCurrentBaseUrl(): String = normalizedBaseUrl

    fun canUseNetwork(): Boolean = networkGate.canUseNetwork()

    fun cancelNetworkRequests() {
        httpClient.dispatcher.cancelAll()
    }

    suspend fun login(password: String, deviceName: String = ""): LoginResponse = withContext(Dispatchers.IO) {
        val payload = LoginRequest(password = password, deviceName = deviceName)
        api.login(payload)
    }

    suspend fun verifyToken(token: String): Boolean = withContext(Dispatchers.IO) {
        try {
            val response = api.verifyToken(token)
            response.valid
        } catch (e: Exception) {
            false
        }
    }

    suspend fun searchBooks(keyword: String): List<SearchResultItem> = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("搜索书籍")
        val encodedKeyword = URLEncoder.encode(keyword.trim(), StandardCharsets.UTF_8.toString())
        val request = Request.Builder()
            .url("${normalizedBaseUrl}api/search?keyword=$encodedKeyword&mode=full")
            .get()
            .build()

        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw IOException("Search request failed: ${response.code}")
            }

            val source = response.body?.source() ?: return@withContext emptyList()
            val deduplicated = LinkedHashMap<String, SearchResultItem>()

            while (true) {
                val line = source.readUtf8Line() ?: break
                if (!line.startsWith("data: ")) {
                    continue
                }
                val payload = line.removePrefix("data: ").trim()
                if (payload.isBlank()) {
                    continue
                }
                if (payload == "[DONE]") {
                    break
                }

                val batch = searchResultListAdapter.fromJson(payload).orEmpty()
                for (item in batch) {
                    if (item.bookUrl.isBlank() || item.sourceUrl.isBlank()) {
                        continue
                    }
                    val resolvedBookKey = resolveBookKey(item.bookKey, item.sourceUrl, item.bookUrl)
                    deduplicated[resolvedBookKey] = item.copy(bookKey = resolvedBookKey)
                }
            }

            deduplicated.values.toList()
        }
    }

    suspend fun addBookToServer(item: SearchResultItem) = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("加入服务器书架")
        api.addBook(
            BookCreateRequest(
                name = item.name,
                author = item.author,
                coverUrl = item.coverUrl,
                intro = item.intro,
                bookUrl = item.bookUrl,
                sourceUrl = item.sourceUrl,
                lastChapter = item.lastChapter,
            )
        )
    }

    suspend fun getBooks(): List<BookItem> = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("拉取服务器书架")
        api.getBooks().map { item ->
            item.copy(bookKey = resolveBookKey(item.bookKey, item.sourceUrl, item.bookUrl))
        }
    }

    suspend fun getBookCategories(): List<BookCategoryItem> = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("拉取服务器分类")
        api.getBookCategories()
    }

    suspend fun createBookCategory(name: String): BookCategoryItem = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("创建分类")
        api.createBookCategory(BookCategoryCreateRequest(name = name))
    }

    suspend fun toggleCategoryHidden(categoryName: String, hidden: Boolean) = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("切换分类隐藏状态")
        api.toggleCategoryHidden(categoryName, BookCategoryHiddenRequest(hidden = hidden))
    }

    suspend fun renameBookCategory(categoryName: String, newName: String) = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("重命名分类")
        api.renameBookCategory(categoryName, BookCategoryRenameRequest(newName = newName))
    }

    suspend fun deleteBookCategory(categoryName: String) = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("删除分类")
        api.deleteBookCategory(categoryName)
    }

    suspend fun setBookCategory(bookId: Int, categoryName: String) = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("设置服务器分类")
        api.setBookCategory(
            bookId = bookId,
            payload = BookCategoryAssignRequest(categoryName = categoryName),
        )
    }

    suspend fun getServerCacheStats(): ServerCacheStats = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("刷新服务器缓存统计")
        api.getServerCacheStats()
    }

    suspend fun clearServerCache(clearAll: Boolean = true): CacheClearResponse = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("清理服务器缓存")
        api.clearServerCache(CacheClearRequest(clearAll = clearAll))
    }

    suspend fun findServerBook(bookUrl: String, sourceUrl: String): BookItem? = withContext(Dispatchers.IO) {
        api.getBooks().firstOrNull {
            it.bookUrl == bookUrl && it.sourceUrl == sourceUrl
        }
    }

    suspend fun getOfflineCatalog(userId: String, deviceId: String): List<OfflineCatalogItem> =
        withContext(Dispatchers.IO) {
            networkGate.requireWifiOnline("拉取服务器离线目录")
            api.getOfflineCatalog(userId = userId, deviceId = deviceId).map { item ->
                item.copy(bookKey = resolveBookKey(item.bookKey, item.sourceUrl, item.bookUrl))
            }
        }

    suspend fun getOfflineTasks(userId: String, deviceId: String, limit: Int = 200): List<OfflineTaskItem> =
        withContext(Dispatchers.IO) {
            networkGate.requireWifiOnline("拉取服务器离线任务")
            api.getOfflineTasks(userId = userId, deviceId = deviceId, limit = limit).map { task ->
                task.copy(bookKey = resolveBookKey(task.bookKey, task.sourceUrl, task.bookUrl))
            }
        }

    suspend fun getClientCacheStats(): ClientCacheStats = withContext(Dispatchers.IO) {
        localStore.getClientCacheStats()
    }

    suspend fun getServerFonts(): List<ServerFontItem> = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("拉取服务器字体")
        api.getServerFonts()
    }

    suspend fun listDownloadedFontFiles(): List<String> = withContext(Dispatchers.IO) {
        if (!localFontDir.exists()) {
            return@withContext emptyList()
        }
        localFontDir.listFiles()
            .orEmpty()
            .filter { file -> file.isFile }
            .sortedBy { file -> file.name.lowercase() }
            .map { file -> file.absolutePath }
    }

    suspend fun downloadServerFont(font: ServerFontItem): String = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("下载服务器字体")
        localFontDir.mkdirs()
        val target = File(localFontDir, font.fileName)
        val responseBody = api.downloadFont(resolveDownloadUrl(font.downloadUrl))
        responseBody.use { body ->
            target.outputStream().use { output ->
                body.byteStream().copyTo(output)
            }
        }
        target.absolutePath
    }

    suspend fun deleteLocalFontFile(path: String): Boolean = withContext(Dispatchers.IO) {
        val target = File(path)
        if (!target.exists() || !target.isFile) {
            return@withContext false
        }

        val fontRoot = localFontDir.canonicalFile
        val targetCanonical = target.canonicalFile
        if (!targetCanonical.path.startsWith(fontRoot.path + File.separator)) {
            return@withContext false
        }

        targetCanonical.delete()
    }

    private fun resolveDownloadUrl(raw: String): String {
        val trimmed = raw.trim()
        if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            return trimmed
        }
        if (trimmed.startsWith("/")) {
            return normalizedBaseUrl.removeSuffix("/") + trimmed
        }
        return normalizedBaseUrl + trimmed
    }

    suspend fun createOfflineTask(payload: OfflineTaskCreateRequest): OfflineTaskItem =
        withContext(Dispatchers.IO) {
            networkGate.requireWifiOnline("创建服务器离线任务")
            api.createOfflineTask(payload).let { task ->
                task.copy(bookKey = resolveBookKey(task.bookKey, task.sourceUrl, task.bookUrl))
            }
        }

    suspend fun getOfflineTask(taskId: String): OfflineTaskItem = withContext(Dispatchers.IO) {
        networkGate.requireWifiOnline("查询服务器离线任务")
        api.getOfflineTask(taskId).let { task ->
            task.copy(bookKey = resolveBookKey(task.bookKey, task.sourceUrl, task.bookUrl))
        }
    }

    suspend fun createServerOfflineTask(
        userId: String,
        deviceId: String,
        bookId: Int? = null,
        bookKey: String? = null,
        bookUrl: String? = null,
        sourceUrl: String? = null,
    ): OfflineTaskItem = withContext(Dispatchers.IO) {
        createOfflineTask(
            OfflineTaskCreateRequest(
                userId = userId,
                deviceId = deviceId,
                bookId = bookId,
                bookKey = bookKey,
                bookUrl = bookUrl,
                sourceUrl = sourceUrl,
            )
        )
    }

    suspend fun awaitOfflineTask(
        taskId: String,
        timeoutMs: Long = 180000L,
        pollIntervalMs: Long = 500L,
        onUpdate: suspend (OfflineTaskItem) -> Unit = {},
    ): OfflineTaskItem {
        val startedAt = System.currentTimeMillis()
        var latest = getOfflineTask(taskId)
        onUpdate(latest)
        while (latest.status == "queued" || latest.status == "running") {
            if (System.currentTimeMillis() - startedAt > timeoutMs) {
                throw IOException("Offline task timed out: $taskId")
            }
            delay(pollIntervalMs)
            latest = getOfflineTask(taskId)
            onUpdate(latest)
        }
        return latest
    }

    suspend fun getChapters(bookKey: String): List<ChapterItem> =
        withContext(Dispatchers.IO) {
            networkGate.requireWifiOnline("拉取章节目录")
            api.getChapters(bookKey = bookKey)
        }

    suspend fun getLocalChapterIndex(bookKey: String): List<ChapterItem> {
        return localStore.listChapterIndex(bookKey).sortedBy { it.idx }
    }

    suspend fun fetchRemoteChapterIndex(book: LocalShelfBook): List<ChapterItem> {
        val chapters = getChapters(book.bookKey).sortedBy { it.idx }
        if (chapters.isNotEmpty()) {
            localStore.seedChapterIndex(book, chapters)
        }
        return chapters
    }

    suspend fun getChapterContent(chapterUrl: String, sourceUrl: String): ChapterContent =
        withContext(Dispatchers.IO) {
            networkGate.requireWifiOnline("拉取章节内容")
            api.getChapterContent(chapterUrl = chapterUrl, sourceUrl = sourceUrl)
        }

    suspend fun getCachedChapterContent(
        bookKey: String,
        chapterIdx: Int,
    ): ChapterContent? {
        val cached = localStore.getCachedChapter(bookKey, chapterIdx) ?: return null
        return ChapterContent(
            type = cached.type,
            content = cached.content,
            images = cached.images,
        )
    }

    suspend fun getLocalBookshelf(): List<LocalShelfBook> {
        return withContext(Dispatchers.IO) {
            localStore.listBookshelf()
        }
    }

    suspend fun ensureLocalShelfBook(searchResult: SearchResultItem): LocalShelfBook {
        val resolvedBookKey = resolveBookKey(searchResult.bookKey, searchResult.sourceUrl, searchResult.bookUrl)
        val existing = localStore.getBookshelfBook(resolvedBookKey)
        val merged = LocalShelfBook(
            bookKey = resolvedBookKey,
            name = if (searchResult.name.isNotBlank()) searchResult.name else existing?.name.orEmpty(),
            author = if (searchResult.author.isNotBlank()) searchResult.author else existing?.author.orEmpty(),
            coverUrl = if (searchResult.coverUrl.isNotBlank()) searchResult.coverUrl else existing?.coverUrl.orEmpty(),
            intro = if (searchResult.intro.isNotBlank()) searchResult.intro else existing?.intro.orEmpty(),
            bookUrl = searchResult.bookUrl,
            sourceUrl = searchResult.sourceUrl,
            sourceName = if (searchResult.sourceName.isNotBlank()) searchResult.sourceName else existing?.sourceName.orEmpty(),
            categoryName = existing?.categoryName ?: "网文",
            cachedChapters = existing?.cachedChapters ?: 0,
            totalChapters = existing?.totalChapters ?: 0,
            lastReadChapter = existing?.lastReadChapter ?: 1,
            lastReadPosition = existing?.lastReadPosition ?: 0.0,
            lastCachedAt = existing?.lastCachedAt ?: 0L,
            addedAt = existing?.addedAt ?: System.currentTimeMillis(),
        )
        localStore.upsertBookshelf(merged)
        return localStore.getBookshelfBook(resolvedBookKey) ?: merged
    }

    suspend fun ensureLocalShelfBook(book: BookItem): LocalShelfBook {
        val resolvedBookKey = resolveBookKey(book.bookKey, book.sourceUrl, book.bookUrl)
        val existing = localStore.getBookshelfBook(resolvedBookKey)
        val merged = LocalShelfBook(
            bookKey = resolvedBookKey,
            name = if (book.name.isNotBlank()) book.name else existing?.name.orEmpty(),
            author = if (book.author.isNotBlank()) book.author else existing?.author.orEmpty(),
            coverUrl = if (book.coverUrl.isNotBlank()) book.coverUrl else existing?.coverUrl.orEmpty(),
            intro = if (book.intro.isNotBlank()) book.intro else existing?.intro.orEmpty(),
            bookUrl = book.bookUrl,
            sourceUrl = book.sourceUrl,
            sourceName = existing?.sourceName ?: "",
            categoryName = if (book.categoryName.isNotBlank()) book.categoryName else (existing?.categoryName ?: "网文"),
            cachedChapters = existing?.cachedChapters ?: 0,
            totalChapters = maxOf(book.totalChapters, existing?.totalChapters ?: 0),
            lastReadChapter = existing?.lastReadChapter ?: 1,
            lastReadPosition = existing?.lastReadPosition ?: 0.0,
            lastCachedAt = existing?.lastCachedAt ?: 0L,
            addedAt = existing?.addedAt ?: System.currentTimeMillis(),
        )
        localStore.upsertBookshelf(merged)
        return localStore.getBookshelfBook(resolvedBookKey) ?: merged
    }

    suspend fun seedLocalChapterIndex(book: LocalShelfBook, chapters: List<ChapterItem>) {
        localStore.seedChapterIndex(book, chapters)
    }

    suspend fun saveChapterToLocalCache(
        book: LocalShelfBook,
        chapter: ChapterItem,
        content: ChapterContent,
        totalChapters: Int,
    ): LocalCacheSummary {
        return localStore.saveCachedChapter(
            book = book,
            chapter = chapter,
            content = content,
            totalChapters = totalChapters,
        )
    }

    suspend fun getLocalCacheSummary(bookKey: String): LocalCacheSummary {
        return localStore.getCacheSummary(bookKey)
    }

    suspend fun cacheBookToLocal(
        book: LocalShelfBook,
        onProgress: suspend (cached: Int, total: Int, failed: Int) -> Unit,
    ): LocalCacheSummary {
        networkGate.requireWifiOnline("缓存书籍到本地")
        val chapters = getChapters(book.bookKey).sortedBy { it.idx }
        if (chapters.isEmpty()) {
            return LocalCacheSummary(total = 0, cached = 0, failed = 0)
        }

        localStore.seedChapterIndex(book, chapters)
        var failed = 0
        val cachedIndexes = localStore.getCachedChapterIndexes(book.bookKey).toMutableSet()
        var cached = cachedIndexes.size
        var processed = cachedIndexes.size
        val missing = chapters.filterNot { cachedIndexes.contains(it.idx) }
        val batchSize = 20

        if (processed > 0) {
            onProgress(cached, chapters.size, failed)
        }

        for (batch in missing.chunked(batchSize)) {
            networkGate.requireWifiOnline("缓存章节到本地")
            val fetchedBatch = coroutineScope {
                batch.map { chapter ->
                    async(Dispatchers.IO) {
                        chapter to runCatching {
                            getChapterContent(chapter.url, book.sourceUrl)
                        }.getOrNull()
                    }
                }.awaitAll()
            }

            val successfulEntries = fetchedBatch.mapNotNull { (chapter, content) ->
                content?.let { chapter to it }
            }
            val batchFailed = fetchedBatch.size - successfulEntries.size

            if (successfulEntries.isNotEmpty()) {
                localStore.saveCachedChaptersBatch(
                    book = book,
                    entries = successfulEntries,
                    totalChapters = chapters.size,
                )
                cached += successfulEntries.size
            }

            failed += batchFailed
            processed += fetchedBatch.size

            if (shouldReportProgress(processed, chapters.size)) {
                onProgress(cached, chapters.size, failed)
            }
        }

        onProgress(cached, chapters.size, failed)

        val finalSummary = localStore.getCacheSummary(book.bookKey)
        return finalSummary.copy(
            total = maxOf(finalSummary.total, chapters.size),
            cached = maxOf(finalSummary.cached, cached),
            failed = failed,
        )
    }

    suspend fun clearLocalCache() {
        localStore.clearAll()
    }

    suspend fun deleteLocalBook(bookKey: String) {
        localStore.deleteBook(bookKey)
    }

    suspend fun updateLocalReadChapter(bookKey: String, chapterNumber: Int) {
        localStore.updateLastReadChapter(bookKey, chapterNumber)
    }

    suspend fun updateLocalReadProgress(bookKey: String, chapterNumber: Int, position: Double) {
        localStore.updateLastReadProgress(bookKey, chapterNumber, position)
    }

    suspend fun upsertSyncProgress(payload: SyncProgressUpsertRequest): SyncProgressItem =
        withContext(Dispatchers.IO) {
            networkGate.requireWifiOnline("同步阅读进度")
            api.upsertSyncProgress(payload).let { item ->
                item.copy(bookKey = resolveBookKey(item.bookKey, item.sourceUrl, item.bookUrl))
            }
        }

    suspend fun pullSyncProgress(userId: String, since: Int, limit: Int = 100): SyncPullResponse =
        withContext(Dispatchers.IO) {
            networkGate.requireWifiOnline("拉取阅读进度")
            val response = api.pullSyncProgress(userId = userId, since = since, limit = limit)
            response.copy(
                items = response.items.map { item ->
                    item.copy(bookKey = resolveBookKey(item.bookKey, item.sourceUrl, item.bookUrl))
                }
            )
        }

    private fun resolveBookKey(rawBookKey: String?, sourceUrl: String, bookUrl: String): String {
        return BookIdentity.resolveBookKey(rawBookKey, sourceUrl, bookUrl)
    }

    companion object {
        private fun shouldReportProgress(processed: Int, total: Int): Boolean {
            if (processed >= total) {
                return true
            }
            return processed % 12 == 0
        }

        fun normalizeBaseUrl(raw: String): String {
            val trimmed = raw.trim()
            val withProtocol = if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
                trimmed
            } else {
                "http://$trimmed"
            }
            return if (withProtocol.endsWith("/")) withProtocol else "$withProtocol/"
        }

    }
}
