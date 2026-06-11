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
import androidx.compose.material3.Button
import androidx.compose.material3.Card
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
import com.easyreader.elinkclient.data.model.OfflineCatalogItem
import com.easyreader.elinkclient.ui.EinkUiState

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun BookshelfPane(
    state: EinkUiState,
    onSelectCategory: (String) -> Unit,
    onSyncServerData: () -> Unit,
    onRefreshLocalShelf: () -> Unit,
    onOpenOfflineBook: (OfflineCatalogItem) -> Unit,
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
            Card(modifier = Modifier.fillMaxWidth()) {
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
                                modifier = Modifier.height(34.dp),
                            ) {
                                Text(if (name == "all") "全部分类" else name)
                            }
                        }
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Button(
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
                key = { it.bookKey },
            ) { book ->
                Card(
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
                            text = "分类 ${book.categoryName} · 阅读章 ${book.lastReadChapter}",
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
                key = { it.bookKey.ifBlank { "${it.id}-${it.bookUrl}" } },
            ) { book ->
                val readingChapter = state.readingChapterByBook[book.bookKey] ?: 1
                Card(
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
                            text = "分类 ${book.categoryName} · 阅读章 ${readingChapter}",
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
                text = "服务器离线目录 (${state.offlineCatalog.size})",
                style = MaterialTheme.typography.titleMedium,
            )
        }

        if (state.offlineCatalog.isEmpty()) {
            item {
                Text(
                    text = "此设备暂无服务器离线任务结果。",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        } else {
            items(
                items = state.offlineCatalog,
                key = { it.bookKey.ifBlank { "${it.bookUrl}|${it.sourceUrl}" } },
            ) { item ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            text = item.name,
                            style = MaterialTheme.typography.bodyLarge,
                        )
                        Text(
                            text = "${item.author.ifBlank { "未知作者" }} · 服务器缓存 ${item.cachedChapters}/${item.totalChapters}",
                            style = MaterialTheme.typography.bodyMedium,
                        )

                        Button(
                            onClick = { onOpenOfflineBook(item) },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(40.dp),
                        ) {
                            Text("阅读")
                        }
                    }
                }
            }
        }
    }

    selectedLocalBook?.let { book ->
        AlertDialog(
            onDismissRequest = { selectedLocalBook = null },
            title = { Text(book.name) },
            text = {
                Text("分类 ${book.categoryName} · 阅读章 ${book.lastReadChapter}")
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
        val readingChapter = state.readingChapterByBook[book.bookKey] ?: 1
        AlertDialog(
            onDismissRequest = { selectedServerBook = null },
            title = { Text(book.name) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("分类 ${book.categoryName} · 阅读章 ${readingChapter}")
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
