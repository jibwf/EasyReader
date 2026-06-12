package com.easyreader.elinkclient.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.clickable
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.easyreader.elinkclient.ui.EinkUiState

@Composable
fun HomePane(
    state: EinkUiState,
    onContinueReading: () -> Unit,
    onOpenLocalBookshelf: () -> Unit,
    onOpenServerBookshelf: () -> Unit,
    onOpenSearch: () -> Unit,
    onSyncServerData: () -> Unit,
    onRefreshLocalShelf: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Text(
                text = "阅读首页",
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
                        text = "继续阅读",
                        style = MaterialTheme.typography.titleSmall,
                    )

                    if (state.activeBookKey.isNullOrBlank()) {
                        Text(
                            text = "当前没有激活的阅读会话。先从书架打开一本书，后续会在这里快速续读。",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        OutlinedButton(onClick = onOpenLocalBookshelf) {
                            Text("前往书架")
                        }
                    } else {
                        val bookKey = state.activeBookKey.orEmpty()
                        val chapterNumber = (state.readingChapterByBook[bookKey] ?: (state.activeChapterListIndex + 1)).coerceAtLeast(1)
                        val position = (state.readingPositionByBook[bookKey] ?: state.activeChapterPosition)
                            .coerceIn(0.0, 1.0)
                        Text(
                            text = state.activeBookName.ifBlank { "未命名书籍" },
                            style = MaterialTheme.typography.bodyLarge,
                        )
                        Text(
                            text = "上次阅读 第 $chapterNumber 章 · ${(position * 100).toInt()}%",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        EinkButton(onClick = onContinueReading) {
                            Text("继续阅读")
                        }
                    }
                }
            }
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
                        text = "内容总览",
                        style = MaterialTheme.typography.titleSmall,
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        SummaryMetric(
                            label = "本地书架",
                            value = state.localBookshelf.size,
                            onClick = onOpenLocalBookshelf,
                        )
                        SummaryMetric(
                            label = "服务器书架",
                            value = state.serverBooks.size,
                            onClick = onOpenServerBookshelf,
                        )
                    }
                }
            }
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
                        text = "快捷操作",
                        style = MaterialTheme.typography.titleSmall,
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        EinkButton(
                            onClick = onRefreshLocalShelf,
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("刷新本地")
                        }
                        OutlinedButton(
                            onClick = onSyncServerData,
                            enabled = state.isNetworkAvailable,
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("同步服务器数据")
                        }
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedButton(
                            onClick = onOpenSearch,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("去搜索")
                        }
                    }
                }
            }
        }

        if (state.localCacheStatusMessage.isNotBlank() || state.lastSyncMessage.isNotBlank()) {
            item {
                EinkCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Text(
                            text = "设备状态",
                            style = MaterialTheme.typography.titleSmall,
                        )
                        if (state.offlineTaskStatusMessage.isNotBlank()) {
                            Text(
                                text = "任务: ${state.offlineTaskStatusMessage}",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                        if (state.localCacheStatusMessage.isNotBlank()) {
                            Text(
                                text = "缓存: ${state.localCacheStatusMessage}",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                        if (state.lastSyncMessage.isNotBlank()) {
                            Text(
                                text = "同步: ${state.lastSyncMessage}",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                        HorizontalDivider()
                        Text(
                            text = "设备 ID: ${state.deviceId}",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SummaryMetric(label: String, value: Int, onClick: (() -> Unit)? = null) {
    Column(
        modifier = if (onClick != null) {
            Modifier.clickable(onClick = onClick)
        } else {
            Modifier
        },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(
            text = value.toString(),
            style = MaterialTheme.typography.titleLarge,
        )
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
        )
    }
}
