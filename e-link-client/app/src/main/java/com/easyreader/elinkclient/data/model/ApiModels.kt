package com.easyreader.elinkclient.data.model

import com.squareup.moshi.Json

data class BookItem(
    val id: Int,
    @Json(name = "book_key") val bookKey: String,
    val name: String,
    val author: String,
    @Json(name = "cover_url") val coverUrl: String,
    val intro: String,
    @Json(name = "book_url") val bookUrl: String,
    @Json(name = "source_url") val sourceUrl: String,
    @Json(name = "category_name") val categoryName: String = "网文",
    @Json(name = "total_chapters") val totalChapters: Int,
)

data class BookCategoryItem(
    val name: String,
    val hidden: Boolean,
    val preset: Boolean,
    @Json(name = "book_count") val bookCount: Int,
)

data class BookCategoryAssignRequest(
    @Json(name = "category_name") val categoryName: String,
)

data class ServerFontItem(
    val id: String,
    val name: String,
    @Json(name = "file_name") val fileName: String,
    val extension: String,
    @Json(name = "size_bytes") val sizeBytes: Long,
    val sha256: String,
    @Json(name = "download_url") val downloadUrl: String,
)

data class ServerCacheStats(
    val books: Int,
    val chapters: Int,
    val bytes: Long,
)

data class CacheClearRequest(
    @Json(name = "clear_all") val clearAll: Boolean = true,
)

data class CacheClearResponse(
    val cleared: Int,
    @Json(name = "clear_all") val clearAll: Boolean,
)

data class ClientCacheStats(
    @Json(name = "chapter_books") val chapterBooks: Int,
    @Json(name = "chapter_entries") val chapterEntries: Int,
    @Json(name = "font_files") val fontFiles: Int,
    val bytes: Long,
)

data class BookCreateRequest(
    val name: String,
    val author: String = "",
    @Json(name = "cover_url") val coverUrl: String = "",
    val intro: String = "",
    @Json(name = "book_url") val bookUrl: String,
    @Json(name = "source_url") val sourceUrl: String,
    @Json(name = "last_chapter") val lastChapter: String = "",
    @Json(name = "total_chapters") val totalChapters: Int = 0,
)

data class SearchResultItem(
    @Json(name = "book_key") val bookKey: String,
    val name: String,
    val author: String = "",
    @Json(name = "cover_url") val coverUrl: String = "",
    val intro: String = "",
    @Json(name = "book_url") val bookUrl: String,
    @Json(name = "source_url") val sourceUrl: String,
    @Json(name = "source_name") val sourceName: String = "",
    @Json(name = "last_chapter") val lastChapter: String = "",
    val kind: String = "",
)

data class LocalShelfBook(
    @Json(name = "book_key") val bookKey: String,
    val name: String,
    val author: String = "",
    @Json(name = "cover_url") val coverUrl: String = "",
    val intro: String = "",
    @Json(name = "book_url") val bookUrl: String,
    @Json(name = "source_url") val sourceUrl: String,
    @Json(name = "source_name") val sourceName: String = "",
    @Json(name = "category_name") val categoryName: String = "网文",
    @Json(name = "cached_chapters") val cachedChapters: Int = 0,
    @Json(name = "total_chapters") val totalChapters: Int = 0,
    @Json(name = "last_read_chapter") val lastReadChapter: Int = 1,
    @Json(name = "last_cached_at") val lastCachedAt: Long = 0L,
    @Json(name = "added_at") val addedAt: Long = System.currentTimeMillis(),
)

data class CachedChapterIndex(
    val idx: Int,
    val title: String,
    val url: String,
    @Json(name = "is_cached") val isCached: Boolean = false,
    val type: String = "novel",
)

data class CachedBookMeta(
    @Json(name = "book_key") val bookKey: String,
    val name: String,
    val author: String = "",
    @Json(name = "book_url") val bookUrl: String,
    @Json(name = "source_url") val sourceUrl: String,
    @Json(name = "total_chapters") val totalChapters: Int = 0,
    @Json(name = "updated_at") val updatedAt: Long = System.currentTimeMillis(),
    val chapters: List<CachedChapterIndex> = emptyList(),
)

data class CachedChapterPayload(
    val idx: Int,
    val title: String,
    val url: String,
    val type: String = "novel",
    val content: String = "",
    val images: List<String> = emptyList(),
    @Json(name = "saved_at") val savedAt: Long = System.currentTimeMillis(),
)

data class LocalCacheSummary(
    val total: Int,
    val cached: Int,
    val failed: Int,
)

data class ChapterItem(
    val title: String,
    val url: String,
    val idx: Int,
)

data class ChapterContent(
    val type: String,
    val content: String = "",
    val images: List<String> = emptyList(),
)

data class SyncProgressUpsertRequest(
    @Json(name = "user_id") val userId: String,
    @Json(name = "device_id") val deviceId: String,
    @Json(name = "book_key") val bookKey: String,
    @Json(name = "book_url") val bookUrl: String,
    @Json(name = "source_url") val sourceUrl: String,
    @Json(name = "book_name") val bookName: String,
    @Json(name = "chapter_idx") val chapterIdx: Int,
    @Json(name = "chapter_title") val chapterTitle: String,
    @Json(name = "chapter_url") val chapterUrl: String,
    val position: Double,
)

data class SyncProgressItem(
    @Json(name = "user_id") val userId: String,
    @Json(name = "device_id") val deviceId: String,
    @Json(name = "book_key") val bookKey: String,
    @Json(name = "book_url") val bookUrl: String,
    @Json(name = "source_url") val sourceUrl: String,
    @Json(name = "book_name") val bookName: String,
    @Json(name = "chapter_idx") val chapterIdx: Int,
    @Json(name = "chapter_title") val chapterTitle: String,
    @Json(name = "chapter_url") val chapterUrl: String,
    val position: Double,
    val revision: Int,
    @Json(name = "updated_at") val updatedAt: String,
)

data class SyncPullResponse(
    val items: List<SyncProgressItem>,
    @Json(name = "next_cursor") val nextCursor: Int,
)

data class OfflineTaskCreateRequest(
    @Json(name = "user_id") val userId: String,
    @Json(name = "device_id") val deviceId: String,
    @Json(name = "book_id") val bookId: Int? = null,
    @Json(name = "book_key") val bookKey: String? = null,
    @Json(name = "book_url") val bookUrl: String? = null,
    @Json(name = "source_url") val sourceUrl: String? = null,
)

data class OfflineTaskItem(
    @Json(name = "task_id") val taskId: String,
    @Json(name = "user_id") val userId: String,
    @Json(name = "device_id") val deviceId: String,
    @Json(name = "book_id") val bookId: Int,
    @Json(name = "book_key") val bookKey: String,
    @Json(name = "book_name") val bookName: String,
    @Json(name = "book_url") val bookUrl: String,
    @Json(name = "source_url") val sourceUrl: String,
    val status: String,
    val progress: Int = 0,
    @Json(name = "total_chapters") val totalChapters: Int,
    @Json(name = "cached_chapters") val cachedChapters: Int,
    @Json(name = "error_message") val errorMessage: String,
    @Json(name = "created_at") val createdAt: String,
    @Json(name = "updated_at") val updatedAt: String,
    @Json(name = "completed_at") val completedAt: String,
)

data class OfflineCatalogItem(
    @Json(name = "user_id") val userId: String,
    @Json(name = "device_id") val deviceId: String,
    @Json(name = "book_id") val bookId: Int,
    @Json(name = "book_key") val bookKey: String,
    @Json(name = "book_url") val bookUrl: String,
    @Json(name = "source_url") val sourceUrl: String,
    val name: String,
    val author: String,
    @Json(name = "total_chapters") val totalChapters: Int,
    @Json(name = "cached_chapters") val cachedChapters: Int,
    @Json(name = "updated_at") val updatedAt: String,
)
