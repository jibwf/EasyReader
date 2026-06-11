package com.easyreader.elinkclient.data.network

import com.easyreader.elinkclient.data.model.BookItem
import com.easyreader.elinkclient.data.model.BookCategoryAssignRequest
import com.easyreader.elinkclient.data.model.BookCategoryItem
import com.easyreader.elinkclient.data.model.BookCreateRequest
import com.easyreader.elinkclient.data.model.CacheClearRequest
import com.easyreader.elinkclient.data.model.CacheClearResponse
import com.easyreader.elinkclient.data.model.ChapterContent
import com.easyreader.elinkclient.data.model.ChapterItem
import com.easyreader.elinkclient.data.model.OfflineCatalogItem
import com.easyreader.elinkclient.data.model.OfflineTaskCreateRequest
import com.easyreader.elinkclient.data.model.OfflineTaskItem
import com.easyreader.elinkclient.data.model.ServerCacheStats
import com.easyreader.elinkclient.data.model.ServerFontItem
import com.easyreader.elinkclient.data.model.SyncProgressItem
import com.easyreader.elinkclient.data.model.SyncProgressUpsertRequest
import com.easyreader.elinkclient.data.model.SyncPullResponse
import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Query
import retrofit2.http.Path
import retrofit2.http.Streaming
import retrofit2.http.Url

interface EasyReaderApi {
    @GET("api/books")
    suspend fun getBooks(): List<BookItem>

    @GET("api/books/categories")
    suspend fun getBookCategories(): List<BookCategoryItem>

    @PUT("api/books/{book_id}/category")
    suspend fun setBookCategory(
        @Path("book_id") bookId: Int,
        @Body payload: BookCategoryAssignRequest,
    ): Map<String, String>

    @GET("api/books/cache/stats")
    suspend fun getServerCacheStats(): ServerCacheStats

    @POST("api/books/cache/clear")
    suspend fun clearServerCache(
        @Body payload: CacheClearRequest,
    ): CacheClearResponse

    @POST("api/books")
    suspend fun addBook(
        @Body payload: BookCreateRequest,
    ): Map<String, String>

    @GET("api/content/chapters")
    suspend fun getChapters(
        @Query("book_key") bookKey: String,
    ): List<ChapterItem>

    @GET("api/content/chapter")
    suspend fun getChapterContent(
        @Query("url") chapterUrl: String,
        @Query("source_url") sourceUrl: String,
    ): ChapterContent

    @POST("api/sync/progress/upsert")
    suspend fun upsertSyncProgress(
        @Body payload: SyncProgressUpsertRequest,
    ): SyncProgressItem

    @GET("api/sync/progress/pull")
    suspend fun pullSyncProgress(
        @Query("user_id") userId: String,
        @Query("since") since: Int,
        @Query("limit") limit: Int,
    ): SyncPullResponse

    @POST("api/offline/tasks")
    suspend fun createOfflineTask(
        @Body payload: OfflineTaskCreateRequest,
    ): OfflineTaskItem

    @GET("api/offline/tasks/{task_id}")
    suspend fun getOfflineTask(
        @Path("task_id") taskId: String,
    ): OfflineTaskItem

    @GET("api/offline/tasks")
    suspend fun getOfflineTasks(
        @Query("user_id") userId: String,
        @Query("device_id") deviceId: String,
        @Query("limit") limit: Int,
    ): List<OfflineTaskItem>

    @GET("api/offline/catalog")
    suspend fun getOfflineCatalog(
        @Query("user_id") userId: String,
        @Query("device_id") deviceId: String,
    ): List<OfflineCatalogItem>

    @GET("api/fonts")
    suspend fun getServerFonts(): List<ServerFontItem>

    @Streaming
    @GET
    suspend fun downloadFont(@Url url: String): ResponseBody
}
