# Changelog

本文档记录 EasyReader 项目的主要变更。

## [2026-06-13] - Phase 1 安全加固与文档更新

### 新增

- **密码认证系统**
  - 新增 `READER_PASSWORD` 环境变量配置登录密码
  - 新增 `READER_TOKEN_EXPIRY_DAYS` 配置 Token 有效期（默认 90 天）
  - 新增 `POST /api/auth/login` 和 `GET /api/auth/verify` 端点
  - 前端新增登录对话框，Token 保存到 localStorage
  - 墨水屏客户端支持 Token 认证

- **文件上传限制**
  - 新增 `READER_MAX_UPLOAD_SIZE_MB` 环境变量（默认 200MB）
  - 书籍导入、备份恢复等端点添加文件大小验证
  - 书源导入列表长度限制为 3000 项

- **CORS 配置**
  - 新增 `READER_CORS_ORIGINS` 环境变量（默认 `*`）
  - 支持配置多个允许的来源

- **安全头**
  - 添加 `X-Content-Type-Options: nosniff`
  - 添加 `X-Frame-Options: DENY`
  - 添加 `X-XSS-Protection: 1; mode=block`
  - 添加 `Referrer-Policy: strict-origin-when-cross-origin`

- **内存泄漏修复**
  - `_SOURCE_HEALTH` 字典添加 LRU 淘汰机制，上限 500 条
  - 使用 `OrderedDict` 实现最近访问优先保留

### 修复

- 替换 5 处废弃的 `asyncio.get_event_loop()` 为 `get_running_loop()`

### 文档更新

- README.md 添加完整的环境变量配置表（13 个变量）
- README.md 补充缺失的 10 个 API 端点文档
- README.md 添加认证配置说明
- docs/phase1.md 更新为 Phase 1 完成状态
- Jun13-audit.md 标记已修复的安全问题

### 测试

- 新增 18 个测试用例（认证、上传限制、CORS、内存泄漏）
- 总测试数达到 110 个

## [2026-06-11] - Phase 1 核心功能完成

### 服务端

- 书源解析引擎（CSS/XPath/JSONPath/Regex/JS）
- 多源搜索与结果排序
- 书架管理与分类系统
- 章节缓存与离线任务
- 多端进度同步与书签同步
- 备份恢复系统
- 字体管理

### Web PWA

- IndexedDB + Workbox 双层缓存
- 流式搜索结果消费
- 自动翻页
- 进度冲突处理
- 备份恢复界面

### 墨水屏客户端

- 本地书架与阅读
- 服务端同步
- 离线任务
- 实体按键翻页
- WiFi 闸门
