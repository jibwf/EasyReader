# EasyReader Phase1 阶段文档

更新时间：2026-06-11

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
```

## 当前已完成功能

### 服务端已完成

- 稳定 `book_key` 资源身份。
- 版本头与客户端类型约束。
- 搜索评分、去重、源健康度、短 TTL 缓存和 `fast/full` 模式。
- `book_key` 维度的进度同步与书签同步。
- SQLite-backed 离线任务层、任务轮询与离线目录汇总。
- 统一字体分发与下载接口。
- 服务端快照备份下载与上传恢复接口（全量/增量 + 冲突策略）。

### Web PWA 已完成

- 在线优先 + 本地缓存增强阅读模型。
- IndexedDB 章节缓存与 Workbox 运行时缓存。
- 搜索 `fast/full` 双模式与流式结果消费。
- 自动翻页。
- 进度冲突提示与 `book_key` 去重补传队列。
- 设置页支持备份下载与上传恢复，并可选择恢复模式和冲突策略。

### 墨水屏客户端当前已完成

- 本地书架、目录、章节缓存以 `book_key` 收敛。
- Android 网络层统一注入 `X-Client-Type`、`X-Client-Version`、`X-API-Contract-Version`。
- 同步 DTO 已显式接住 `accepted`、`conflict`、`conflict_reason`，并支持 `force=true` 强制覆盖。
- 待补传队列按书收敛；冲突不再走成功路径；本地会保存最后阅读章节和章节内位置。
- WiFi 闸门和网络状态感知。
- 本地阅读优先路径与未缓存章节显式入口。
- 自动翻页、刷新模式、字体下载与本地字体应用。
- 服务端离线任务创建、任务轮询与本地章节落盘链路。
- `/api/offline/tasks*` 与 `/api/offline/catalog` 已在 Repository、状态层和 UI 上分离。
- 服务器离线任务状态与设备本地落盘状态分别建模和展示。
- 实体按键翻页已经接入阅读器状态机。

## 当前阶段结论

当前 Phase1 不再需要继续补 Android 主流程能力边界；“契约补齐、同步闭环、离线任务闭环、阅读器与设备闭环”已经完成实现收口。

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

1. “创建任务并前台等待完成”的链路已经改成显式任务状态机。
2. 服务端缓存阶段与设备本地落盘阶段已经拆分为两个状态源。
3. `/api/offline/tasks*` 与 `/api/offline/catalog` 已各自回到自己的语义边界。

### 4. 阅读器与设备闭环（已完成）

1. 阅读路径继续保持只读本地缓存章节，不在阅读链路里隐式拉取远端正文。
2. 未缓存章节已经补上明确入口，允许回目录或触发本地缓存更新。
3. 自动翻页、阅读器可见性、实体按键入口和刷新策略已经接入统一状态机。

## 当前阶段剩余收尾

1. 在真实墨水屏设备上回归 WiFi 闸门、自动翻页、目录跳转、实体按键和刷新策略协同。
2. 补齐 Android `assembleDebug`、`assembleRelease` 的产物验证。
3. 如需发版，补一次跨端同步冲突和离线任务的端到端人工验收。

## 当前阶段验收口径

功能验收：

- WiFi 关闭时，不发生隐式联网。
- 已缓存章节稳定可读。
- 重新进入书籍时，可恢复到章节内位置。
- 待补传队列按书收敛。
- 冲突回包不会被当作成功同步吞掉。
- 离线任务状态和离线目录摘要不再混淆。
- 自动翻页、目录跳转、实体按键和刷新策略协同正常。

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

## 维护约束

- 架构或共享 API 约束变更，先更新 `docs/architecture.md`。
- Phase1 状态和下一步方案变化，先更新 `docs/phase1.md`。
- 墨水屏客户端架构变更，先更新 `e-link-client/docs/eink-client-plan.md`。