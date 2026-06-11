package com.easyreader.elinkclient.data.local

import android.content.Context
import com.easyreader.elinkclient.core.BookIdentity
import com.easyreader.elinkclient.data.model.CachedBookMeta
import com.easyreader.elinkclient.data.model.CachedChapterIndex
import com.easyreader.elinkclient.data.model.CachedChapterPayload
import com.easyreader.elinkclient.data.model.ChapterContent
import com.easyreader.elinkclient.data.model.ChapterItem
import com.easyreader.elinkclient.data.model.ClientCacheStats
import com.easyreader.elinkclient.data.model.LocalCacheSummary
import com.easyreader.elinkclient.data.model.LocalShelfBook
import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File
import java.security.MessageDigest

class LocalCacheStore(
    context: Context,
    moshi: Moshi,
) {
    private val mutex = Mutex()
    private val rootDir = File(context.filesDir, "eink-local-store")
    private val bookshelfFile = File(rootDir, "bookshelf.json")

    private val bookshelfType = Types.newParameterizedType(List::class.java, LocalShelfBook::class.java)
    private val bookshelfAdapter = moshi.adapter<List<LocalShelfBook>>(bookshelfType)
    private val metaAdapter = moshi.adapter(CachedBookMeta::class.java)
    private val chapterAdapter = moshi.adapter(CachedChapterPayload::class.java)

    suspend fun listBookshelf(): List<LocalShelfBook> = withContext(Dispatchers.IO) {
        mutex.withLock {
            ensureRootLocked()
            readBookshelfLocked()
        }
    }

    suspend fun upsertBookshelf(book: LocalShelfBook): List<LocalShelfBook> = withContext(Dispatchers.IO) {
        mutex.withLock {
            ensureRootLocked()
            val current = readBookshelfLocked().toMutableList()
            val index = current.indexOfFirst {
                it.bookKey == book.bookKey
            }
            if (index >= 0) {
                val existing = current[index]
                val mergedLastReadChapter = if (book.lastReadChapter > 0) {
                    book.lastReadChapter
                } else {
                    existing.lastReadChapter
                }
                val mergedLastReadPosition = when {
                    mergedLastReadChapter == book.lastReadChapter && mergedLastReadChapter == existing.lastReadChapter -> {
                        maxOf(normalizeProgress(book.lastReadPosition), normalizeProgress(existing.lastReadPosition))
                    }
                    mergedLastReadChapter == book.lastReadChapter -> normalizeProgress(book.lastReadPosition)
                    else -> normalizeProgress(existing.lastReadPosition)
                }
                current[index] = book.copy(
                    addedAt = existing.addedAt,
                    cachedChapters = maxOf(book.cachedChapters, existing.cachedChapters),
                    totalChapters = maxOf(book.totalChapters, existing.totalChapters),
                    lastReadChapter = mergedLastReadChapter,
                    lastReadPosition = mergedLastReadPosition,
                    lastCachedAt = maxOf(book.lastCachedAt, existing.lastCachedAt),
                )
            } else {
                current += book
            }

            val sorted = current.sortedByDescending { it.addedAt }
            writeBookshelfLocked(sorted)
            sorted
        }
    }

    suspend fun getBookshelfBook(bookKey: String): LocalShelfBook? = withContext(Dispatchers.IO) {
        mutex.withLock {
            ensureRootLocked()
            readBookshelfLocked().firstOrNull {
                it.bookKey == bookKey
            }
        }
    }

    suspend fun seedChapterIndex(
        book: LocalShelfBook,
        chapters: List<ChapterItem>,
    ): CachedBookMeta = withContext(Dispatchers.IO) {
        mutex.withLock {
            ensureRootLocked()
            val existing = readMetaLocked(book.bookKey)
            val existingMap = existing?.chapters?.associateBy { it.idx }.orEmpty()

            val mergedChapters = chapters.sortedBy { it.idx }.map { chapter ->
                val prev = existingMap[chapter.idx]
                CachedChapterIndex(
                    idx = chapter.idx,
                    title = chapter.title,
                    url = chapter.url,
                    isCached = prev?.isCached ?: false,
                    type = prev?.type ?: "novel",
                )
            }

            val meta = CachedBookMeta(
                bookKey = book.bookKey,
                name = book.name,
                author = book.author,
                bookUrl = book.bookUrl,
                sourceUrl = book.sourceUrl,
                totalChapters = maxOf(chapters.size, existing?.totalChapters ?: 0),
                updatedAt = System.currentTimeMillis(),
                chapters = mergedChapters,
            )
            writeMetaLocked(meta)
            val cachedCount = mergedChapters.count { it.isCached }
            updateBookshelfStatsLocked(
                bookKey = book.bookKey,
                cachedChapters = cachedCount,
                totalChapters = meta.totalChapters,
                timestamp = System.currentTimeMillis(),
            )
            meta
        }
    }

    suspend fun listChapterIndex(bookKey: String): List<ChapterItem> = withContext(Dispatchers.IO) {
        mutex.withLock {
            ensureRootLocked()
            val meta = readMetaLocked(bookKey) ?: return@withLock emptyList()
            meta.chapters.sortedBy { it.idx }.map {
                ChapterItem(
                    title = it.title,
                    url = it.url,
                    idx = it.idx,
                    isCached = it.isCached,
                )
            }
        }
    }

    suspend fun getCachedChapter(
        bookKey: String,
        chapterIdx: Int,
    ): CachedChapterPayload? = withContext(Dispatchers.IO) {
        mutex.withLock {
            ensureRootLocked()
            val chapterFile = chapterFileLocked(bookKey, chapterIdx)
            if (!chapterFile.exists()) {
                return@withLock null
            }
            runCatching {
                val raw = chapterFile.readText(Charsets.UTF_8)
                chapterAdapter.fromJson(raw)
            }.getOrNull()
        }
    }

    suspend fun getCachedChapterIndexes(bookKey: String): Set<Int> = withContext(Dispatchers.IO) {
        mutex.withLock {
            ensureRootLocked()
            val meta = readMetaLocked(bookKey) ?: return@withLock emptySet()
            meta.chapters.asSequence()
                .filter { it.isCached }
                .map { it.idx }
                .toSet()
        }
    }

    suspend fun saveCachedChapter(
        book: LocalShelfBook,
        chapter: ChapterItem,
        content: ChapterContent,
        totalChapters: Int,
    ): LocalCacheSummary = withContext(Dispatchers.IO) {
        mutex.withLock {
            ensureRootLocked()
            val payload = CachedChapterPayload(
                idx = chapter.idx,
                title = chapter.title,
                url = chapter.url,
                type = content.type,
                content = content.content,
                images = content.images,
                savedAt = System.currentTimeMillis(),
            )
            val file = chapterFileLocked(book.bookKey, chapter.idx)
            file.parentFile?.mkdirs()
            writeTextAtomic(file, chapterAdapter.toJson(payload))

            val currentMeta = readMetaLocked(book.bookKey)
            val mutableChapters = currentMeta?.chapters?.toMutableList() ?: mutableListOf()
            val idx = mutableChapters.indexOfFirst { it.idx == chapter.idx }
            val updatedIndex = CachedChapterIndex(
                idx = chapter.idx,
                title = chapter.title,
                url = chapter.url,
                isCached = true,
                type = content.type,
            )
            if (idx >= 0) {
                mutableChapters[idx] = updatedIndex
            } else {
                mutableChapters += updatedIndex
            }
            val sortedChapters = mutableChapters.sortedBy { it.idx }
            val meta = CachedBookMeta(
                bookKey = book.bookKey,
                name = book.name,
                author = book.author,
                bookUrl = book.bookUrl,
                sourceUrl = book.sourceUrl,
                totalChapters = maxOf(totalChapters, currentMeta?.totalChapters ?: 0, sortedChapters.size),
                updatedAt = System.currentTimeMillis(),
                chapters = sortedChapters,
            )
            writeMetaLocked(meta)

            val cachedCount = sortedChapters.count { it.isCached }
            val summary = LocalCacheSummary(
                total = meta.totalChapters,
                cached = cachedCount,
                failed = 0,
            )

            updateBookshelfStatsLocked(
                bookKey = book.bookKey,
                cachedChapters = summary.cached,
                totalChapters = summary.total,
                timestamp = System.currentTimeMillis(),
            )
            summary
        }
    }

    suspend fun saveCachedChaptersBatch(
        book: LocalShelfBook,
        entries: List<Pair<ChapterItem, ChapterContent>>,
        totalChapters: Int,
    ): LocalCacheSummary = withContext(Dispatchers.IO) {
        mutex.withLock {
            ensureRootLocked()
            if (entries.isEmpty()) {
                val meta = readMetaLocked(book.bookKey)
                    ?: return@withLock LocalCacheSummary(total = 0, cached = 0, failed = 0)
                return@withLock LocalCacheSummary(
                    total = meta.totalChapters,
                    cached = meta.chapters.count { it.isCached },
                    failed = 0,
                )
            }

            val currentMeta = readMetaLocked(book.bookKey)
            val chapterMap = currentMeta?.chapters
                ?.associateBy { it.idx }
                ?.toMutableMap()
                ?: mutableMapOf()

            for ((chapter, content) in entries) {
                val payload = CachedChapterPayload(
                    idx = chapter.idx,
                    title = chapter.title,
                    url = chapter.url,
                    type = content.type,
                    content = content.content,
                    images = content.images,
                    savedAt = System.currentTimeMillis(),
                )
                val file = chapterFileLocked(book.bookKey, chapter.idx)
                file.parentFile?.mkdirs()
                writeTextAtomic(file, chapterAdapter.toJson(payload))

                chapterMap[chapter.idx] = CachedChapterIndex(
                    idx = chapter.idx,
                    title = chapter.title,
                    url = chapter.url,
                    isCached = true,
                    type = content.type,
                )
            }

            val sortedChapters = chapterMap.values.sortedBy { it.idx }
            val meta = CachedBookMeta(
                bookKey = book.bookKey,
                name = book.name,
                author = book.author,
                bookUrl = book.bookUrl,
                sourceUrl = book.sourceUrl,
                totalChapters = maxOf(totalChapters, currentMeta?.totalChapters ?: 0, sortedChapters.size),
                updatedAt = System.currentTimeMillis(),
                chapters = sortedChapters,
            )
            writeMetaLocked(meta)

            val cachedCount = sortedChapters.count { it.isCached }
            val summary = LocalCacheSummary(
                total = meta.totalChapters,
                cached = cachedCount,
                failed = 0,
            )

            updateBookshelfStatsLocked(
                bookKey = book.bookKey,
                cachedChapters = summary.cached,
                totalChapters = summary.total,
                timestamp = System.currentTimeMillis(),
            )

            summary
        }
    }

    suspend fun getCacheSummary(bookKey: String): LocalCacheSummary = withContext(Dispatchers.IO) {
        mutex.withLock {
            ensureRootLocked()
            val meta = readMetaLocked(bookKey)
            if (meta == null) {
                return@withLock LocalCacheSummary(total = 0, cached = 0, failed = 0)
            }
            LocalCacheSummary(
                total = meta.totalChapters,
                cached = meta.chapters.count { it.isCached },
                failed = 0,
            )
        }
    }

    suspend fun clearAll(): Unit = withContext(Dispatchers.IO) {
        mutex.withLock {
            if (rootDir.exists()) {
                rootDir.deleteRecursively()
            }
            rootDir.mkdirs()
        }
    }

    suspend fun deleteBook(bookKey: String): Unit = withContext(Dispatchers.IO) {
        mutex.withLock {
            ensureRootLocked()
            val books = readBookshelfLocked().filterNot {
                it.bookKey == bookKey
            }
            writeBookshelfLocked(books)

            val bookDir = bookDirLocked(bookKey)
            if (bookDir.exists()) {
                bookDir.deleteRecursively()
            }
        }
    }

    suspend fun updateLastReadChapter(bookKey: String, chapterNumber: Int): Unit = withContext(Dispatchers.IO) {
        updateLastReadProgress(bookKey, chapterNumber, 0.0)
    }

    suspend fun updateLastReadProgress(bookKey: String, chapterNumber: Int, position: Double): Unit = withContext(Dispatchers.IO) {
        mutex.withLock {
            ensureRootLocked()
            val normalized = chapterNumber.coerceAtLeast(1)
            val normalizedPosition = normalizeProgress(position)
            val books = readBookshelfLocked().toMutableList()
            val index = books.indexOfFirst {
                it.bookKey == bookKey
            }
            if (index < 0) {
                return@withLock
            }
            books[index] = books[index].copy(
                lastReadChapter = normalized,
                lastReadPosition = normalizedPosition,
            )
            writeBookshelfLocked(books.sortedByDescending { it.addedAt })
        }
    }

    suspend fun getClientCacheStats(): ClientCacheStats = withContext(Dispatchers.IO) {
        mutex.withLock {
            ensureRootLocked()
            val booksDir = File(rootDir, "books")
            val fontDir = File(rootDir, "fonts")

            val chapterBooks = booksDir.listFiles().orEmpty().count { it.isDirectory }
            val chapterEntries = booksDir.walkTopDown()
                .filter { file ->
                    file.isFile && file.name.startsWith("chapter_") && file.name.endsWith(".json")
                }
                .count()
            val fontFiles = fontDir.listFiles().orEmpty().count { it.isFile }

            val bytes = rootDir.walkTopDown()
                .filter { it.isFile }
                .sumOf { it.length() }

            ClientCacheStats(
                chapterBooks = chapterBooks,
                chapterEntries = chapterEntries,
                fontFiles = fontFiles,
                bytes = bytes,
            )
        }
    }

    private fun ensureRootLocked() {
        if (!rootDir.exists()) {
            rootDir.mkdirs()
        }
    }

    private fun readBookshelfLocked(): List<LocalShelfBook> {
        if (!bookshelfFile.exists()) {
            return emptyList()
        }
        val raw = bookshelfFile.readText(Charsets.UTF_8)
        val parsed = runCatching { bookshelfAdapter.fromJson(raw).orEmpty() }.getOrDefault(emptyList())
        return parsed.map { book ->
            val resolvedBookKey = BookIdentity.resolveBookKey(book.bookKey, book.sourceUrl, book.bookUrl)
            book.copy(
                bookKey = resolvedBookKey,
                lastReadChapter = book.lastReadChapter.coerceAtLeast(1),
                lastReadPosition = normalizeProgress(book.lastReadPosition),
            )
        }
    }

    private fun writeBookshelfLocked(books: List<LocalShelfBook>) {
        bookshelfFile.parentFile?.mkdirs()
        val deduplicated = LinkedHashMap<String, LocalShelfBook>()
        for (book in books.sortedBy { it.addedAt }) {
            val resolvedBookKey = BookIdentity.resolveBookKey(book.bookKey, book.sourceUrl, book.bookUrl)
            deduplicated[resolvedBookKey] = book.copy(
                bookKey = resolvedBookKey,
                lastReadChapter = book.lastReadChapter.coerceAtLeast(1),
                lastReadPosition = normalizeProgress(book.lastReadPosition),
            )
        }
        val normalized = deduplicated.values.sortedByDescending { it.addedAt }
        writeTextAtomic(bookshelfFile, bookshelfAdapter.toJson(normalized))
    }

    private fun normalizeProgress(position: Double): Double {
        if (!position.isFinite()) {
            return 0.0
        }
        return position.coerceIn(0.0, 1.0)
    }

    private fun readMetaLocked(
        bookKey: String,
    ): CachedBookMeta? {
        val targetFile = metaFileLocked(bookKey)
        if (!targetFile.exists()) {
            return null
        }

        val parsed = runCatching { metaAdapter.fromJson(targetFile.readText(Charsets.UTF_8)) }.getOrNull() ?: return null
        return parsed.copy(
            bookKey = BookIdentity.resolveBookKey(parsed.bookKey, parsed.sourceUrl, parsed.bookUrl),
        )
    }

    private fun writeMetaLocked(meta: CachedBookMeta) {
        val normalizedBookKey = BookIdentity.resolveBookKey(meta.bookKey, meta.sourceUrl, meta.bookUrl)
        val file = metaFileLocked(normalizedBookKey)
        file.parentFile?.mkdirs()
        writeTextAtomic(file, metaAdapter.toJson(meta.copy(bookKey = normalizedBookKey)))
    }

    private fun updateBookshelfStatsLocked(
        bookKey: String,
        cachedChapters: Int,
        totalChapters: Int,
        timestamp: Long,
    ) {
        val books = readBookshelfLocked().toMutableList()
        val index = books.indexOfFirst { it.bookKey == bookKey }
        if (index < 0) {
            return
        }
        val current = books[index]
        books[index] = current.copy(
            cachedChapters = cachedChapters,
            totalChapters = maxOf(totalChapters, current.totalChapters),
            lastCachedAt = timestamp,
        )
        writeBookshelfLocked(books.sortedByDescending { it.addedAt })
    }

    private fun metaFileLocked(bookKey: String): File {
        val dir = bookDirLocked(bookKey)
        return File(dir, "meta.json")
    }

    private fun chapterFileLocked(bookKey: String, chapterIdx: Int): File {
        val dir = File(bookDirLocked(bookKey), "chapters")
        return File(dir, "chapter_${chapterIdx}.json")
    }

    private fun bookDirLocked(bookKey: String): File {
        val key = digestKey("book_key:$bookKey")
        return File(rootDir, "books/$key")
    }

    private fun digestKey(raw: String): String {
        val digest = MessageDigest.getInstance("SHA-1").digest(raw.toByteArray(Charsets.UTF_8))
        val builder = StringBuilder(digest.size * 2)
        for (b in digest) {
            builder.append(String.format("%02x", b))
        }
        return builder.toString()
    }

    private fun writeTextAtomic(file: File, text: String) {
        file.parentFile?.mkdirs()
        val tempFile = File(file.parentFile, "${file.name}.tmp")
        tempFile.writeText(text, Charsets.UTF_8)
        if (file.exists() && !file.delete()) {
            tempFile.delete()
            throw IllegalStateException("Unable to replace ${file.name}")
        }
        if (!tempFile.renameTo(file)) {
            tempFile.delete()
            throw IllegalStateException("Unable to commit ${file.name}")
        }
    }
}
