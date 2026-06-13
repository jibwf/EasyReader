package com.easyreader.elinkclient.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
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
import com.easyreader.elinkclient.ui.EinkUiState

@Composable
fun SettingsPane(
    state: EinkUiState,
    onApplyConfig: (String, String) -> Unit,
    onCycleSyncMode: () -> Unit,
    onManualSyncProgress: () -> Unit,
    onResolveSyncConflictUseRemote: () -> Unit,
    onForceSyncConflictLocal: () -> Unit,
    onRefreshOfflineDiagnostics: () -> Unit,
    onPullRemoteProgress: () -> Unit,
    onPullServerBookshelf: () -> Unit,
    onCycleRefreshMode: () -> Unit,
    onRefreshCacheStats: () -> Unit,
    onClearServerCache: () -> Unit,
    onApplyReaderFont: (String) -> Unit,
    onDownloadAndApplyFont: (ServerFontItem) -> Unit,
    onDeleteLocalFont: (String) -> Unit,
    onRefreshFonts: () -> Unit,
    onClearClientCache: () -> Unit,
    onCancelOfflineDownload: () -> Unit,
    onClearError: () -> Unit,
    onLogin: (String) -> Unit,
    onLogout: () -> Unit,
) {
    var editableBaseUrl by remember { mutableStateOf(state.baseUrl) }
    var editableUserId by remember { mutableStateOf(state.userId) }
    var editablePassword by remember { mutableStateOf("") }

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
            EinkCard(modifier = Modifier.fillMaxWidth()) {
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
                    EinkButton(
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
            EinkCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        text = "认证管理",
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Text(
                        text = "设置密码保护系统访问。登录后 Token 保存在本地，90 天内无需重新输入。",
                        style = MaterialTheme.typography.bodySmall,
                    )

                    if (state.authToken.isNotBlank()) {
                        Text(
                            text = "已登录",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        OutlinedButton(
                            onClick = onLogout,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(40.dp),
                        ) {
                            Text("退出登录")
                        }
                    } else {
                        OutlinedTextField(
                            value = editablePassword,
                            onValueChange = { editablePassword = it },
                            label = { Text("输入密码") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth(),
                        )
                        EinkButton(
                            onClick = {
                                if (editablePassword.isNotBlank()) {
                                    onLogin(editablePassword)
                                    editablePassword = ""
                                }
                            },
                            enabled = editablePassword.isNotBlank() && state.isNetworkAvailable,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(42.dp),
                        ) {
                            Text("登录")
                        }
                    }

                    if (state.authMessage.isNotBlank()) {
                        Text(
                            text = state.authMessage,
                            style = MaterialTheme.typography.bodySmall,
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
                        EinkButton(
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
            EinkCard(modifier = Modifier.fillMaxWidth()) {
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
                        EinkButton(
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
            EinkCard(modifier = Modifier.fillMaxWidth()) {
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
                            text = "离线诊断",
                            style = MaterialTheme.typography.titleSmall,
                        )
                        OutlinedButton(
                            onClick = onRefreshOfflineDiagnostics,
                            enabled = state.isNetworkAvailable,
                            modifier = Modifier.height(50.dp),
                        ) {
                            Text("刷新")
                        }
                    }

                    if (state.offlineCatalog.isEmpty()) {
                        Text(
                            text = "暂无服务器离线目录诊断数据，需要时手动刷新。",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    } else {
                        Text(
                            text = "服务器离线目录 ${state.offlineCatalog.size} 项",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        state.offlineCatalog.take(5).forEach { item ->
                            Text(
                                text = "${item.name} · ${item.cachedChapters}/${item.totalChapters}",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                        if (state.offlineCatalog.size > 5) {
                            Text(
                                text = "其余 ${state.offlineCatalog.size - 5} 项已省略",
                                style = MaterialTheme.typography.bodySmall,
                            )
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

                state.syncConflict?.let { conflict ->
                    EinkCard(modifier = Modifier.fillMaxWidth()) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(10.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Text(
                                text = "同步冲突待处理",
                                style = MaterialTheme.typography.titleSmall,
                            )
                            Text(
                                text = conflict.summary,
                                style = MaterialTheme.typography.bodySmall,
                            )
                            Text(
                                text = "本地 -> 第 ${conflict.local.chapterIdx + 1} 章 · 位置 ${"%.2f".format(conflict.local.position)}",
                                style = MaterialTheme.typography.bodySmall,
                            )
                            Text(
                                text = "云端 -> 第 ${conflict.remote.chapterIdx + 1} 章 · 位置 ${"%.2f".format(conflict.remote.position)}",
                                style = MaterialTheme.typography.bodySmall,
                            )
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                OutlinedButton(
                                    onClick = onResolveSyncConflictUseRemote,
                                    modifier = Modifier.weight(1f),
                                ) {
                                    Text("采用云端")
                                }
                                EinkButton(
                                    onClick = onForceSyncConflictLocal,
                                    enabled = state.isNetworkAvailable,
                                    modifier = Modifier.weight(1f),
                                ) {
                                    Text("采用本地")
                                }
                            }
                        }
                    }
                }

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

                EinkButton(
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

                Text(
                    text = "待补传进度 ${state.pendingSyncCount} 本",
                    style = MaterialTheme.typography.bodySmall,
                )
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
                            modifier = Modifier.height(50.dp),
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
                                EinkCard(modifier = Modifier.fillMaxWidth()) {
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
                                                EinkButton(
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
            EinkCard(modifier = Modifier.fillMaxWidth()) {
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
                state.activeOfflineTask?.let { task ->
                    Text(
                        text = "当前服务器任务: ${task.bookName} · ${task.status} ${task.progress}%",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                state.activeLocalCache?.let { cache ->
                    Text(
                        text = "当前本地落盘: ${cache.bookName} · ${cache.cachedChapters}/${cache.totalChapters} · 失败 ${cache.failedChapters}",
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
