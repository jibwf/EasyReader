package com.easyreader.elinkclient.data.offline

import com.easyreader.elinkclient.data.model.LocalCacheSummary
import com.easyreader.elinkclient.data.model.LocalShelfBook
import com.easyreader.elinkclient.data.model.OfflineTaskItem
import com.easyreader.elinkclient.data.repository.ReaderRepository
import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

data class OfflineDownloadResult(
    val shelfBook: LocalShelfBook,
    val serverTask: OfflineTaskItem,
    val localSummary: LocalCacheSummary,
)

class OfflineDownloadManager(
    private val repository: ReaderRepository,
) {
    private var activeJob: Job? = null

    val isActive: Boolean
        get() = activeJob?.isActive == true

    fun cancel() {
        activeJob?.cancel()
        activeJob = null
    }

    fun start(
        scope: CoroutineScope,
        prepareBook: suspend () -> LocalShelfBook,
        createServerTask: suspend (LocalShelfBook) -> OfflineTaskItem,
        onServerTaskUpdate: suspend (book: LocalShelfBook, task: OfflineTaskItem) -> Unit,
        onLocalProgress: suspend (book: LocalShelfBook, cached: Int, total: Int, failed: Int) -> Unit,
        onComplete: suspend (OfflineDownloadResult) -> Unit,
        onError: suspend (Throwable) -> Unit,
    ) {
        cancel()
        activeJob = scope.launch {
            runCatching {
                val shelfBook = prepareBook()
                val initialTask = createServerTask(shelfBook)
                val serverTask = repository.awaitOfflineTask(initialTask.taskId) { task ->
                    onServerTaskUpdate(shelfBook, task)
                }
                if (serverTask.status != "completed") {
                    throw IOException(serverTask.errorMessage.ifBlank { "服务器离线任务 ${serverTask.status}" })
                }
                val summary = repository.cacheBookToLocal(shelfBook) { cached, total, failed ->
                    onLocalProgress(shelfBook, cached, total, failed)
                }
                OfflineDownloadResult(
                    shelfBook = shelfBook,
                    serverTask = serverTask,
                    localSummary = summary,
                )
            }.onSuccess { result ->
                activeJob = null
                onComplete(result)
            }.onFailure { error ->
                activeJob = null
                if (error is CancellationException) {
                    onError(error)
                } else {
                    onError(error)
                }
            }
        }
    }
}