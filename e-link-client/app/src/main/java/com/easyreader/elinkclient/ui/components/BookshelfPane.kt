package com.easyreader.elinkclient.ui.components

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.easyreader.elinkclient.data.model.BookItem
import com.easyreader.elinkclient.data.model.LocalShelfBook
import com.easyreader.elinkclient.ui.EinkUiState

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun BookshelfPane(
    state: EinkUiState,
    onSelectCategory: (String) -> Unit,
    onSyncServerData: () -> Unit,
    onRefreshLocalShelf: () -> Unit,
    onOpenLocalBook: (LocalShelfBook) -> Unit,
    onOfflineLocalBook: (LocalShelfBook) -> Unit,
    onDeleteLocalBook: (LocalShelfBook) -> Unit,
    onOpenServerBook: (BookItem) -> Unit,
    onOfflineServerBook: (BookItem) -> Unit,
    onQueueOfflineTask: (BookItem) -> Unit,
) {
    var selectedLocalBook by remember { mutableStateOf<LocalShelfBook?>(null) }
    var selectedServerBook by remember { mutableStateOf<BookItem?>(null) }

    val categoryItems = remember(state.bookCategories) {
        listOf("all") + state.bookCategories.map { it.name }
    }
    val visibleServerBooks = remember(state.serverBooks, state.selectedCategory) {
        if (state.selectedCategory == "all") {
            state.serverBooks
        } else {
            state.serverBooks.filter { it.categoryName == state.selectedCategory }
        }
    }
    val visibleLocalBooks = remember(state.localBookshelf, state.selectedCategory) {
        if (state.selectedCategory == "all") {
            state.localBookshelf
        } else {
            state.localBookshelf.filter { it.categoryName == state.selectedCategory }
        }
    }
    val serverByBookKey = remember(state.serverBooks) {
        state.serverBooks.associateBy { it.bookKey }
    }

    LazyColumn(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Text(
                text = "书架",
                style = MaterialTheme.typography.titleMedium,
            )
        }

        item {
            EinkCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        text = "同步入口",
                        style = MaterialTheme.typography.titleSmall,
                    )

                    LazyRow(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        items(categoryItems, key = { it }) { name ->
                            OutlinedButton(
                                onClick = { onSelectCategory(name) },
                                modifier = Modifier.height(50.dp),
                            ) {
                                Text(if (name == "all") "全部分类" else name)
                            }
                        }
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        EinkButton(
                            onClick = onRefreshLocalShelf,
                            modifier = Modifier
                                .weight(1f)
                                .height(42.dp),
                        ) {
                            Text("刷新本地")
                        }
                        OutlinedButton(
                            onClick = onSyncServerData,
                            enabled = state.isNetworkAvailable,
                            modifier = Modifier
                                .weight(1f)
                                .height(42.dp),
                        ) {
                            Text("同步服务器数据")
                        }
                    }
                }
            }
        }

        item {
            Text(
                text = "本地书架 (${visibleLocalBooks.size})",
                style = MaterialTheme.typography.titleMedium,
            )
        }

        if (visibleLocalBooks.isEmpty()) {
            item {
                Text(
                    text = "当前分类下本地书架为空。可在搜索页导入，或从服务器书架添加到本地。",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        } else {
            items(
                items = visibleLocalBooks,
                key = { localShelfItemKey(it) },
            ) { book ->
                val serverBook = serverByBookKey[book.bookKey]
                val sourceTotalChapters = serverBook?.totalChapters ?: book.totalChapters
                val serverCachedChapters = serverBook?.serverCachedChapters ?: 0
                val localProgressText = "本地进度 第 ${book.lastReadChapter.coerceAtLeast(1)} 章 · ${formatProgressPercent(book.lastReadPosition)}"
                EinkCard(
                    modifier = Modifier
                        .fillMaxWidth()
                        .combinedClickable(
                            onClick = { onOpenLocalBook(book) },
                            onLongClick = { selectedLocalBook = book },
                        ),
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            text = book.name,
                            style = MaterialTheme.typography.bodyLarge,
                        )
                        Text(
                            text = "分类 ${book.categoryName} · $localProgressText",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Text(
                            text = "服务器缓存 ${serverCachedChapters}/${sourceTotalChapters.coerceAtLeast(0)} · 本地缓存 ${book.cachedChapters}/${book.totalChapters.coerceAtLeast(0)}",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
        }

        item {
            HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
        }

        item {
            Text(
                text = "服务器书架 (${visibleServerBooks.size})",
                style = MaterialTheme.typography.titleMedium,
            )
        }

        if (visibleServerBooks.isEmpty()) {
            item {
                Text(
                    text = "当前分类下服务器书架为空。",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        } else {
            items(
                items = visibleServerBooks,
                key = { serverShelfItemKey(it) },
            ) { book ->
                val remoteChapter = state.remoteReadingChapterByBook[book.bookKey]
                val remotePosition = state.remoteReadingPositionByBook[book.bookKey] ?: 0.0
                val remoteProgressText = if (remoteChapter != null) {
                    "云端进度 第 ${remoteChapter.coerceAtLeast(1)} 章 · ${formatProgressPercent(remotePosition)}"
                } else {
                    "云端进度 暂无"
                }
                EinkCard(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { selectedServerBook = book },
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            text = book.name,
                            style = MaterialTheme.typography.bodyLarge,
                        )
                        Text(
                            text = "分类 ${book.categoryName} · $remoteProgressText",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Text(
                            text = "服务器缓存 ${book.serverCachedChapters}/${book.totalChapters.coerceAtLeast(0)}",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
        }
    }

    selectedLocalBook?.let { book ->
        val serverBook = serverByBookKey[book.bookKey]
        val sourceTotalChapters = serverBook?.totalChapters ?: book.totalChapters
        val serverCachedChapters = serverBook?.serverCachedChapters ?: 0
        val localProgressText = "本地进度 第 ${book.lastReadChapter.coerceAtLeast(1)} 章 · ${formatProgressPercent(book.lastReadPosition)}"
        AlertDialog(
            onDismissRequest = { selectedLocalBook = null },
            tonalElevation = 0.dp,
            title = { Text(book.name) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("分类 ${book.categoryName} · $localProgressText")
                    Text("服务器缓存 ${serverCachedChapters}/${sourceTotalChapters.coerceAtLeast(0)} · 本地缓存 ${book.cachedChapters}/${book.totalChapters.coerceAtLeast(0)}")
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        selectedLocalBook = null
                        onOfflineLocalBook(book)
                    },
                ) {
                    Text("更新本地缓存")
                }
            },
            confirmButton = {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(
                        onClick = {
                            selectedLocalBook = null
                            onDeleteLocalBook(book)
                        },
                    ) {
                        Text("删除本书")
                    }
                    TextButton(
                        onClick = {
                            selectedLocalBook = null
                            onOpenLocalBook(book)
                        },
                    ) {
                        Text("阅读")
                    }
                }
            },
        )
    }

    selectedServerBook?.let { book ->
        val remoteChapter = state.remoteReadingChapterByBook[book.bookKey]
        val remotePosition = state.remoteReadingPositionByBook[book.bookKey] ?: 0.0
        val remoteProgressText = if (remoteChapter != null) {
            "云端进度 第 ${remoteChapter.coerceAtLeast(1)} 章 · ${formatProgressPercent(remotePosition)}"
        } else {
            "云端进度 暂无"
        }
        AlertDialog(
            onDismissRequest = { selectedServerBook = null },
            tonalElevation = 0.dp,
            title = { Text(book.name) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("分类 ${book.categoryName} · $remoteProgressText")
                    Text("服务器缓存 ${book.serverCachedChapters}/${book.totalChapters.coerceAtLeast(0)}")
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        selectedServerBook = null
                        onQueueOfflineTask(book)
                    },
                        enabled = state.isNetworkAvailable,
                ) {
                    Text("服务器缓存")
                }
            },
            confirmButton = {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(
                        onClick = {
                            selectedServerBook = null
                            onOfflineServerBook(book)
                        },
                        enabled = state.isNetworkAvailable,
                    ) {
                        Text("缓存到本地")
                    }
                    TextButton(
                        onClick = {
                            selectedServerBook = null
                            onOpenServerBook(book)
                        },
                    ) {
                        Text("阅读")
                    }
                }
            },
        )
    }
}

internal fun localShelfItemKey(book: LocalShelfBook): String {
    return buildSectionKey(
        prefix = "local",
        stablePart = book.bookKey,
        fallback = "${book.bookUrl}|${book.sourceUrl}|${book.name}",
    )
}

internal fun serverShelfItemKey(book: BookItem): String {
    return buildSectionKey(
        prefix = "server",
        stablePart = book.bookKey,
        fallback = "${book.id}|${book.bookUrl}|${book.sourceUrl}",
    )
}

private fun buildSectionKey(prefix: String, stablePart: String, fallback: String): String {
    val resolved = stablePart.ifBlank { fallback }
    return "$prefix:$resolved"
}

private fun formatProgressPercent(position: Double): String {
    val normalized = position.coerceIn(0.0, 1.0)
    return "${(normalized * 100).toInt()}%"
}
