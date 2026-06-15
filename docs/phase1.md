# EasyReader Phase1 阶段文档

更新时间：2026-06-13

## 文档目的

这份文档统一记录当前 Phase1 的三类内容：

- 当前已经完成的部署形态。
- 当前已经完成的功能范围。
- 当前阶段的下一步方案与验收口径。

它不负责系统架构和客户端分层说明；这些内容分别放在 `docs/architecture.md` 和 `e-link-client/docs/eink-client-plan.md`。

## Phase1 当前定位

经过本轮实现收口，当前阶段的判断已经很明确：

- 服务端重构已经完成。
- Web PWA 重构已经完成。
- 墨水屏客户端四条主线已经完成实现闭环，当前重点转向联调验收、真机回归和打包验证。
- ✅ 安全加固已经完成（密码认证、文件上传限制、CORS 配置、内存泄漏修复）。

## 当前已完成部署

当前已经完成并固化的部署形态是单容器部署：

- 前端在构建阶段打包为静态文件。
- FastAPI 在运行时同时提供 `/api/*` 和前端 SPA 回退。
- 运行期数据写入 `data/` volume。
- 服务端统一管理 SQLite、缓存目录、导出目录和字体目录。

当前部署拓扑：

```text
Browser / PWA      ->  FastAPI  -> SQLite
E-link Android     ->  FastAPI  -> data/cache
                                -> data/exports
                                -> data/fonts
                                -> data/audiobooks
```

## 当前已完成功能

### 服务端已完成

- ✅ 稳定 `book_key` 资源身份。
- ✅ 版本头与客户端类型约束。
- ✅ 搜索评分、去重、源健康度、短 TTL 缓存和 `fast/full` 模式。
- ✅ `book_key` 维度的进度同步与书签同步。
- ✅ SQLite-backed 离线任务层、任务轮询与离线目录汇总。
- ✅ 统一字体分发与下载接口。
- ✅ 服务端快照备份下载与上传恢复接口（全量/增量 + 冲突策略）。
- ✅ **密码认证系统**：`READER_PASSWORD` 环境变量，Token 90天有效。
- ✅ **安全加固**：文件上传限制（200MB/3000项）、CORS 可配置、内存泄漏修复。
- ✅ **有声书服务**：扫描导入、ZIP 导入、列表查询、删除、媒体文件流式传输（Range 请求支持）。

### Web PWA 已完成

- ✅ 在线优先 + 本地缓存增强阅读模型。
- ✅ IndexedDB 章节缓存与 Workbox 运行时缓存。
- ✅ 搜索 `fast/full` 双模式与流式结果消费。
- ✅ 自动翻页。
- ✅ 进度冲突提示与 `book_key` 去重补传队列。
- ✅ 设置页支持备份下载与上传恢复，并可选择恢复模式和冲突策略。
- ✅ **登录对话框**：首次访问输入密码，Token 保存到 localStorage。
- ✅ **有声书模块**：独立的功能模块，支持磁盘扫描和 ZIP 导入，音频/视频混合播放，MediaSession 后台播放，定时关闭功能。

### 墨水屏客户端当前已完成

- ✅ 本地书架、目录、章节缓存以 `book_key` 收敛。
- ✅ Android 网络层统一注入 `X-Client-Type`、`X-Client-Version`、`X-API-Contract-Version`。
- ✅ 同步 DTO 已显式接住 `accepted`、`conflict`、`conflict_reason`，并支持 `force=true` 强制覆盖。
- ✅ 待补传队列按书收敛；冲突不再走成功路径；本地会保存最后阅读章节和章节内位置。
- ✅ WiFi 闸门和网络状态感知。
- ✅ 本地阅读优先路径与未缓存章节显式入口。
- ✅ 自动翻页、刷新模式、字体下载与本地字体应用。
- ✅ 服务端离线任务创建、任务轮询与本地章节落盘链路。
- ✅ `/api/offline/tasks*` 与 `/api/offline/catalog` 已在 Repository、状态层和 UI 上分离。
- ✅ 服务器离线任务状态与设备本地落盘状态分别建模和展示。
- ✅ 实体按键翻页已经接入阅读器状态机。

## 当前阶段结论

当前 Phase1 不再需要继续补 Android 主流程能力边界；"契约补齐、同步闭环、离线任务闭环、阅读器与设备闭环"已经完成实现收口。

当前剩余工作主要是端到端验收、真机回归和构建产物验证，而不是继续改服务端/PWA 或重新设计 Android 主链路。

## 本轮收口完成项

### 1. 契约补齐（已完成）

1. Android 网络层已经统一注入 `X-Client-Type`、`X-Client-Version`、`X-API-Contract-Version`。
2. 同步 DTO 已显式接住 `accepted`、`conflict`、`conflict_reason`，与服务端当前契约对齐。
3. `book_key` 已固化为 Android 端本地书架、同步、离线与缓存路径的主身份。

### 2. 同步闭环（已完成）

1. 待补传队列继续按书收敛，只保留每本书的最后有效进度。
2. 当服务端返回冲突时，客户端进入显式冲突处理，而不是继续走成功路径。
3. 本地细粒度阅读位置模型已经接入，重新进入书籍时可以恢复到章节内位置。

### 3. 离线任务闭环（已完成）

1. "创建任务并前台等待完成"的链路已经改成显式任务状态机。
2. 服务端缓存阶段与设备本地落盘阶段已经拆分为两个状态源。
3. `/api/offline/tasks*` 与 `/api/offline/catalog` 已各自回到自己的语义边界。

### 4. 阅读器与设备闭环（已完成）

1. 阅读路径继续保持只读本地缓存章节，不在阅读链路里隐式拉取远端正文。
2. 未缓存章节已经补上明确入口，允许回目录或触发本地缓存更新。
3. 自动翻页、阅读器可见性、实体按键入口和刷新策略已经接入统一状态机。

### 5. 安全加固（已完成）

1. ✅ 密码认证系统：`READER_PASSWORD` 环境变量，Token 90天有效。
2. ✅ 文件上传限制：默认 200MB，列表 3000 项。
3. ✅ CORS 配置：`READER_CORS_ORIGINS` 环境变量。
4. ✅ 内存泄漏修复：`_SOURCE_HEALTH` LRU 淘汰，上限 500 条。
5. ✅ 安全头：`X-Content-Type-Options`、`X-Frame-Options`、`X-XSS-Protection`、`Referrer-Policy`。
6. ✅ 废弃 API 修复：`asyncio.get_event_loop()` → `get_running_loop()`。

## 当前阶段剩余收尾

1. 在真实墨水屏设备上回归 WiFi 闸门、自动翻页、目录跳转、实体按键和刷新策略协同。
2. 补齐 Android `assembleDebug`、`assembleRelease` 的产物验证。
3. 如需发版，补一次跨端同步冲突和离线任务的端到端人工验收。
4. ⚠️ 前端测试覆盖（当前零测试）。
5. ⚠️ 速率限制中间件。
6. ⚠️ SSRF 防护。

## 当前阶段验收口径

功能验收：

- WiFi 关闭时，不发生隐式联网。
- 已缓存章节稳定可读。
- 重新进入书籍时，可恢复到章节内位置。
- 待补传队列按书收敛。
- 冲突回包不会被当作成功同步吞掉。
- 离线任务状态和离线目录摘要不再混淆。
- 自动翻页、目录跳转、实体按键和刷新策略协同正常。
- ✅ 设置密码后，未认证请求返回 401。

构建验收目标：

```bash
./.venv/bin/python -m pytest tests/
```

```bash
cd frontend && npm run build
```

```bash
cd e-link-client && JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest :app:assembleDebug --no-daemon
```

```bash
cd e-link-client && JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:assembleRelease --no-daemon
```

本轮已完成 Android 切片验证：

```bash
cd e-link-client && JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon
```

```bash
cd e-link-client && JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --no-daemon
```

## 测试覆盖

### 后端测试（110 个用例）

| 模块 | 测试数 | 覆盖内容 |
|------|--------|----------|
| 规则引擎 | 23 | CSS/XPath/JSONPath/Regex 解析器、JS 引擎、URL 解析器 |
| 搜索服务 | 11 | Legado 源解析、搜索排序、缓存、去重、超时 |
| 内容服务 | 7 | 目录解析、内容解析、服务器缓存回退 |
| 同步/离线 | 7 | 进度同步、书签同步、离线任务、幂等性 |
| 书籍管理 | 8 | TXT/EPUB 导入、批量操作、分类管理 |
| API 契约 | 4 | 版本端点、响应字段验证 |
| 备份恢复 | 2 | 全量/增量恢复、冲突策略 |
| 数据库 | 3 | Schema 验证、唯一约束、默认分类 |
| HTTP 抓取 | 3 | curl_cffi 回退、TLS 重试 |
| 源兼容性 | 6 | 4 种 Legado 格式 + Tauri 格式 |
| 认证 | 12 | 登录、Token 验证、中间件保护 |
| 安全 | 13 | 上传限制、CORS、内存泄漏、API 废弃修复 |

### 前端测试

⚠️ **当前零测试** - 这是第二阶段需要补充的重点。

## 维护约束

- 架构或共享 API 约束变更，先更新 `docs/architecture.md`。
- Phase1 状态和下一步方案变化，先更新 `docs/phase1.md`。
- 墨水屏客户端架构变更，先更新 `e-link-client/docs/eink-client-plan.md`。