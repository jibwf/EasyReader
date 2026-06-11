package com.easyreader.elinkclient.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.easyreader.elinkclient.data.model.SearchResultItem
import com.easyreader.elinkclient.ui.EinkUiState

@Composable
fun SearchPane(
    state: EinkUiState,
    onSearchKeywordChanged: (String) -> Unit,
    onSearchBooks: () -> Unit,
    onImportSearchResult: (SearchResultItem) -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Text(
                text = "搜索",
                style = MaterialTheme.typography.titleMedium,
            )
        }

        item {
            Text(
                text = "输入书名或作者关键词，从服务器搜索后可直接导入本地并离线缓存。",
                style = MaterialTheme.typography.bodySmall,
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
                    OutlinedTextField(
                        value = state.searchKeyword,
                        onValueChange = onSearchKeywordChanged,
                        singleLine = true,
                        label = { Text("书名或作者") },
                        modifier = Modifier.fillMaxWidth(),
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Button(
                            onClick = onSearchBooks,
                            enabled = state.isNetworkAvailable,
                            modifier = Modifier
                                .weight(1f)
                                .height(42.dp),
                        ) {
                            Text("服务器搜索")
                        }
                        OutlinedButton(
                            onClick = { onSearchKeywordChanged("") },
                            modifier = Modifier
                                .weight(1f)
                                .height(42.dp),
                        ) {
                            Text("清空关键词")
                        }
                    }
                }
            }
        }

        item {
            Text(
                text = "结果 ${state.searchResults.size}",
                style = MaterialTheme.typography.bodyMedium,
            )
        }

        if (state.searchResults.isEmpty()) {
            item {
                Text(
                    text = "暂无搜索结果。",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        } else {
            items(
                items = state.searchResults,
                key = { it.bookKey.ifBlank { "${it.sourceUrl}|${it.bookUrl}" } },
            ) { result ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            text = buildString {
                                appendLine(result.name)
                                appendLine(result.author.ifBlank { "未知作者" })
                                if (result.sourceName.isNotBlank()) {
                                    append(result.sourceName)
                                }
                            },
                            style = MaterialTheme.typography.bodyMedium,
                        )

                        Button(
                            onClick = { onImportSearchResult(result) },
                            enabled = state.isNetworkAvailable,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(40.dp),
                        ) {
                            Text("加入书架并离线")
                        }
                    }
                }
            }
        }
    }
}
