# 有声书模块代码审计报告

## [S1] 审计范围

- `backend/services/audiobook.py` (571行)
- `backend/services/douban_cover.py` (327行)
- `backend/routers/audiobook.py` (93行)
- `backend/routers/media.py` (54行)
- `frontend/src/pages/Audiobook.tsx` (324行)
- `frontend/src/pages/AudiobookPlayer.tsx` (348行)
- `frontend/src/stores/audiobookOffline.ts` (224行)
- `frontend/src/stores/audiobookHistory.ts` (45行)
- `frontend/src/components/reader/AudiobookControls.tsx` (394行)

## [S2] 架构问题

### 2.1 重复代码（严重）

`import_audiobook_from_dir()` 和 `_import_root_level_audiobook()` 有大量重复逻辑（约80%相同）。应提取公共函数。

### 2.2 扫描函数过长（中等）

`scan_audiobooks()` 函数超过130行，包含文件夹扫描、根目录处理、孤立记录检测三个独立职责。应拆分为独立函数。

### 2.3 缺少事务管理（严重）

数据库操作分散在多个函数中，部分有 `db.commit()`，部分没有。删除操作的事务不完整。

## [S3] 逻辑问题

### 3.1 删除有声书时未清理 chapter_cache（严重）

`delete_audiobook()` 只删除 `books` 表记录，未删除 `chapters` 和 `chapter_cache` 表中的相关记录。虽有外键级联删除，但 SQLite 默认不启用。

### 3.2 封面下载失败无重试（中等）

`_fetch_cover_for_audiobook()` 失败后不重试，用户只能重新扫描。

### 3.3 转码后删除原文件（危险）

`_transcode_to_compatible()` 在转码成功后删除原文件（`file_path.unlink()`），这是不可逆操作。

## [S4] UI/UX 问题

### 4.1 播放器缺少封面显示

`AudiobookPlayer.tsx` 只显示耳机图标，不显示书籍封面。有声书应有沉浸式封面展示。

### 4.2 定时关闭功能不完整

`AudiobookControls.tsx` 的定时关闭只暂停播放，不保存进度。用户可能丢失播放位置。

### 4.3 缺少播放列表/收藏功能

底部栏有"目录"和"收藏"按钮，但点击无响应（`onClick` 为空）。

### 4.4 进度条不支持触摸拖动

`handleProgressMouseDown` 只处理鼠标事件，移动端无法拖动进度条。

## [S5] 性能问题

### 5.1 每次扫描都重新获取封面

即使封面已存在，扫描时仍会检查并可能重新下载。应增加缓存过期机制。

### 5.2 章节列表无分页

`list_audiobooks()` 一次加载所有有声书，数据量大时可能卡顿。

## [S6] 安全问题

### 6.1 未验证媒体文件路径

`serve_media()` 中的 `folder_name` 和 `filename` 虽然检查了 `..`，但未验证实际文件是否在 `audiobook_dir` 内，可能存在路径遍历风险。

### 6.2 封面文件名基于 MD5

`_download_cover()` 使用 MD5 哈希生成文件名，但未验证文件是否已存在，可能被覆盖。

## [S7] 优化建议（优先级排序）

| 优先级 | 问题 | 建议 |
|--------|------|------|
| P0 | 删除未清理缓存 | 添加级联删除或手动清理 |
| P0 | 路径遍历风险 | 验证文件路径在允许目录内 |
| P1 | 重复代码 | 提取 `_import_audiobook_core()` 公共函数 |
| P1 | 扫描函数过长 | 拆分为 `_scan_subfolders()`, `_scan_root_files()`, `_detect_orphans()` |
| P1 | 进度条不支持触摸 | 添加 touchstart/touchmove/touchend 事件 |
| P2 | 播放器缺少封面 | 在播放器显示书籍封面作为背景 |
| P2 | 定时关闭不保存进度 | 暂停前调用 `saveProgress()` |
| P2 | 收藏功能未实现 | 实现收藏列表和播放 |
| P3 | 章节列表分页 | 大量章节时虚拟滚动 |

## [S8] 最佳实践对比

| 特性 | 当前状态 | 最佳实践 |
|------|----------|----------|
| 离线缓存 | Cache API + Zustand | ✓ 正确 |
| 播放历史 | Zustand persist | ✓ 正确 |
| 媒体格式检测 | ffprobe | ✓ 正确 |
| 封面获取 | 豆瓣搜索 | ✓ 正确（可增加其他源） |
| 进度保存 | 30秒定时 + 离开页面 | ✓ 正确 |
| MediaSession | 已实现 | ✓ 正确 |
| 睡眠定时器 | 已实现 | ✓ 正确 |
| 倍速播放 | 已实现 | ✓ 正确 |

## [S9] 总结

有声书模块整体架构合理，核心功能（扫描、导入、播放、离线缓存）已实现。主要问题集中在：

1. **数据完整性**：删除操作未清理关联数据
2. **代码复用**：导入逻辑重复
3. **UI 完善**：收藏功能、封面显示、触摸支持
4. **安全性**：路径验证需加强

建议按 P0 → P1 → P2 → P3 顺序逐步优化。
