package com.easyreader.elinkclient.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.easyreader.elinkclient.data.model.ServerFontItem
import com.easyreader.elinkclient.ui.AutoPageTurnSpeed
import com.easyreader.elinkclient.ui.EinkUiState

@Composable
fun SettingsPane(
    state: EinkUiState,
    onApplyConfig: (String, String) -> Unit,
    onCycleSyncMode: () -> Unit,
    onManualSyncProgress: () -> Unit,
    onPullRemoteProgress: () -> Unit,
    onPullServerBookshelf: () -> Unit,
    onCycleRefreshMode: () -> Unit,
    onToggleAutoPageTurn: () -> Unit,
    onSetAutoPageTurnSpeed: (AutoPageTurnSpeed) -> Unit,
    onRefreshCacheStats: () -> Unit,
    onClearServerCache: () -> Unit,
    onApplyReaderFont: (String) -> Unit,
    onDownloadAndApplyFont: (ServerFontItem) -> Unit,
    onDeleteLocalFont: (String) -> Unit,
    onRefreshFonts: () -> Unit,
    onClearClientCache: () -> Unit,
    onCancelOfflineDownload: () -> Unit,
    onClearError: () -> Unit,
) {
    var editableBaseUrl by remember { mutableStateOf(state.baseUrl) }
    var editableUserId by remember { mutableStateOf(state.userId) }

    LaunchedEffect(state.baseUrl, state.userId) {
        editableBaseUrl = state.baseUrl
        editableUserId = state.userId
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 4.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Text(
            text = "设置",
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
                    text = "连接配置",
                    style = MaterialTheme.typography.titleSmall,
                )

                OutlinedTextField(
                    value = editableBaseUrl,
                    onValueChange = { editableBaseUrl = it },
                    label = { Text("服务器地址") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )

                OutlinedTextField(
                    value = editableUserId,
                    onValueChange = { editableUserId = it },
                    label = { Text("用户 ID") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )

                Text(
                    text = "设备 ID: ${state.deviceId}",
                    style = MaterialTheme.typography.bodySmall,
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Button(
                        onClick = { onApplyConfig(editableBaseUrl, editableUserId) },
                        modifier = Modifier
                            .weight(1f)
                            .height(42.dp),
                    ) {
                        Text("保存配置")
                    }
                    OutlinedButton(
                        onClick = onRefreshCacheStats,
                        modifier = Modifier
                            .weight(1f)
                            .height(42.dp),
                    ) {
                        Text("刷新缓存统计")
                    }
                }
            }
        }
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
                        text = "服务器缓存",
                        style = MaterialTheme.typography.titleSmall,
                    )

                    Text(
                        text = "书籍 ${state.serverCacheStats.books} · 章节 ${state.serverCacheStats.chapters} · ${formatBytes(state.serverCacheStats.bytes)}",
                        style = MaterialTheme.typography.bodySmall,
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedButton(
                            onClick = onRefreshCacheStats,
                            modifier = Modifier
                                .weight(1f)
                                .height(40.dp),
                        ) {
                            Text("刷新")
                        }
                        Button(
                            onClick = onClearServerCache,
                            enabled = state.isNetworkAvailable,
                            modifier = Modifier
                                .weight(1f)
                                .height(40.dp),
                        ) {
                            Text("清理服务器缓存")
                        }
                    }

                    if (state.serverCacheMessage.isNotBlank()) {
                        Text(
                            text = state.serverCacheMessage,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
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
                        text = "本地缓存",
                        style = MaterialTheme.typography.titleSmall,
                    )

                    Text(
                        text = "书籍 ${state.clientCacheStats.chapterBooks} · 章节 ${state.clientCacheStats.chapterEntries} · 字体 ${state.clientCacheStats.fontFiles} · ${formatBytes(state.clientCacheStats.bytes)}",
                        style = MaterialTheme.typography.bodySmall,
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedButton(
                            onClick = onRefreshCacheStats,
                            modifier = Modifier
                                .weight(1f)
                                .height(40.dp),
                        ) {
                            Text("刷新")
                        }
                        Button(
                            onClick = onClearClientCache,
                            modifier = Modifier
                                .weight(1f)
                                .height(40.dp),
                        ) {
                            Text("清理本地缓存")
                        }
                    }

                    if (state.clientCacheMessage.isNotBlank()) {
                        Text(
                            text = state.clientCacheMessage,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
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
                    text = "同步操作",
                    style = MaterialTheme.typography.titleSmall,
                )

                OutlinedButton(
                    onClick = onCycleSyncMode,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(40.dp),
                ) {
                    Text("进度策略: ${state.syncMode.label}（点击切换）")
                }
                Text(
                    text = "网络状态: ${state.networkMode.label}",
                    style = MaterialTheme.typography.bodySmall,
                )

                if (state.offlineDownloadActive) {
                    OutlinedButton(
                        onClick = onCancelOfflineDownload,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(40.dp),
                    ) {
                        Text("取消离线缓存")
                    }
                }

                Button(
                    onClick = onManualSyncProgress,
                    enabled = state.isNetworkAvailable,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(40.dp),
                ) {
                    Text("手动同步当前阅读进度")
                }
                OutlinedButton(
                    onClick = onPullRemoteProgress,
                    enabled = state.isNetworkAvailable,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(40.dp),
                ) {
                    Text("拉取云端进度")
                }
                OutlinedButton(
                    onClick = onPullServerBookshelf,
                    enabled = state.isNetworkAvailable,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(40.dp),
                ) {
                    Text("拉取服务器书架")
                }
                OutlinedButton(
                    onClick = onCycleRefreshMode,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(40.dp),
                ) {
                    Text("刷新模式: ${state.refreshMode.label}（点击切换）")
                }

                OutlinedButton(
                    onClick = onToggleAutoPageTurn,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(40.dp),
                ) {
                    Text(
                        if (state.autoPageTurnEnabled) {
                            "自动翻页: 已开启（点击暂停）"
                        } else {
                            "自动翻页: 已暂停（点击开始）"
                        }
                    )
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    AutoPageTurnSpeed.entries.forEach { speed ->
                        OutlinedButton(
                            onClick = { onSetAutoPageTurnSpeed(speed) },
                            modifier = Modifier
                                .weight(1f)
                                .height(38.dp),
                        ) {
                            Text(if (state.autoPageTurnSpeed == speed) "${speed.label}速*" else "${speed.label}速")
                        }
                    }
                }

                Text(
                    text = "待补传进度 ${state.pendingSyncCount} 本",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
        }

        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(
                            text = "阅读字体",
                            style = MaterialTheme.typography.titleSmall,
                        )
                        OutlinedButton(
                            onClick = onRefreshFonts,
                            enabled = state.isNetworkAvailable,
                            modifier = Modifier.height(34.dp),
                        ) {
                            Text("刷新")
                        }
                    }

                    if (state.readerFonts.isEmpty()) {
                        Text("暂无字体（可将 ttf/otf 放入服务端字体目录后点击刷新）", style = MaterialTheme.typography.bodySmall)
                    } else {
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            state.readerFonts.forEach { font ->
                                val isBuiltIn = font.key.startsWith("builtin:")
                                val isLocalOnly = font.key.startsWith("local:")
                                Card(modifier = Modifier.fillMaxWidth()) {
                                    Column(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(10.dp),
                                        verticalArrangement = Arrangement.spacedBy(6.dp),
                                    ) {
                                        Text(
                                            text = font.name,
                                            style = MaterialTheme.typography.bodyMedium,
                                        )
                                        Text(
                                            text = if (font.fromServer) {
                                                if (font.downloaded) "服务器字体（已下载）" else "服务器字体（未下载）"
                                            } else if (isLocalOnly) {
                                                "本地字体（仅客户端）"
                                            } else {
                                                "系统内置字体"
                                            },
                                            style = MaterialTheme.typography.bodySmall,
                                        )
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                                        ) {
                                            if (font.fromServer && !font.downloaded && font.serverMeta != null) {
                                                Button(
                                                    onClick = { onDownloadAndApplyFont(font.serverMeta) },
                                                    enabled = state.isNetworkAvailable,
                                                    modifier = Modifier.weight(1f),
                                                ) {
                                                    Text("下载并应用")
                                                }
                                            } else {
                                                OutlinedButton(
                                                    onClick = { onApplyReaderFont(font.key) },
                                                    modifier = Modifier.weight(1f),
                                                ) {
                                                    Text(if (state.readerFontKey == font.key) "当前使用" else "应用")
                                                }
                                                if (!isBuiltIn && !font.filePath.isNullOrBlank()) {
                                                    OutlinedButton(
                                                        onClick = { onDeleteLocalFont(font.filePath) },
                                                        modifier = Modifier.weight(1f),
                                                    ) {
                                                        Text("删除本地")
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        item {
            Card(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = "设备状态",
                    style = MaterialTheme.typography.titleSmall,
                )
                Text(
                    text = "Sync Cursor: ${state.syncCursor}",
                    style = MaterialTheme.typography.bodySmall,
                )
                Text(
                    text = "Last Sync Revision: ${state.lastSyncRevision}",
                    style = MaterialTheme.typography.bodySmall,
                )
                Text(
                    text = "状态: ${state.lastSyncMessage}",
                    style = MaterialTheme.typography.bodySmall,
                )
                if (state.localCacheStatusMessage.isNotBlank()) {
                    Text(
                        text = "缓存: ${state.localCacheStatusMessage}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
        }

        if (!state.errorMessage.isNullOrBlank()) {
            item {
                OutlinedButton(
                onClick = onClearError,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(40.dp),
                ) {
                    Text("清除错误")
                }
            }
        }

        item { androidx.compose.foundation.layout.Spacer(modifier = Modifier.height(8.dp)) }
    }
}

private fun formatBytes(bytes: Long): String {
    if (bytes < 1024L) return "${bytes}B"
    if (bytes < 1024L * 1024L) return String.format("%.1fKB", bytes / 1024.0)
    return String.format("%.1fMB", bytes / 1024.0 / 1024.0)
}
