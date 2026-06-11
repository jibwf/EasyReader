# EasyReader 下一阶段执行计划

更新时间：2026-06-11

## 文档目的

这份文档用于把本轮整体重构方案固化为可执行清单，供后续开发直接按阶段推进。

适用范围：

- 服务端核心重构（资源身份、搜索、同步、任务层）。
- Web PWA 与墨水屏客户端分轨演进。
- 有声书能力接入。

不在本计划内：

- RSS。
- 漫画路线扩展。
- 重型账号 / 权限系统。

## 全局原则

- 文档只写真实已落地能力和明确排期能力，不把愿景写成现状。
- 服务端是共享内容与共享状态中心，不承担客户端 UI 状态。
- PWA 保持在线优先 + 本地缓存增强；墨水屏端保持本地阅读优先。
- 维持单容器部署，不引入多容器任务系统。
- 本轮重构允许破坏式收口：不要求兼容旧客户端、旧版本和旧数据。

## 建议阅读顺序

1. `docs/architecture.md`：系统边界与角色分工。
2. `docs/client-server-contract.md`：当前 API 契约与语义基线。
3. `docs/next-stage-execution-plan.md`：执行步骤与验收口径。
4. `e-link-client/docs/eink-client-plan.md`：墨水屏端实施细则。

## Phase 0：契约冻结与基线校准（P0，1-2 天）

1. 以 `docs/client-server-contract.md` 作为唯一当前 API 契约源，逐项核对 `/api/version`、`/api/books`、`/api/content/*`、`/api/sync/*`、`/api/offline/*`、`/api/fonts*`。
2. 固化多端请求/响应版本约定：
   - 响应头：`X-Server-Version`、`X-API-Contract-Version`、`X-Supported-Client-Types`
   - 客户端请求头：`X-Client-Type`、`X-Client-Version`、`X-API-Contract-Version`
3. 补契约烟测，覆盖版本端点、书架字段、进度 upsert/pull、离线任务/目录、字体列表。
4. 明确锁定当前身份模型：客户端自管 `user_id + device_id`，不在 P0/P1 引入统一账号系统。
5. 输出验收：后端测试、前端构建、Android Debug 构建、Docker 构建通过。

## Phase 1：资源身份与同步幂等（P0，1-2 周）

1. 引入稳定 `book_key`（建议由规范化 `source_url + book_url` 生成）。
2. 重建关键表主键/唯一键策略：books、chapters、chapter_cache、sync_progress、sync_bookmarks、offline 相关表。
3. 书架、内容、搜索、离线目录、同步响应统一返回 `book_key`。
4. 进度同步唯一键切换为 `user_id + book_key`。
5. 补冲突测试：章节回退、同章位置回退、`force=true` 覆盖、revision 行为。
6. PWA 与墨水屏端模型切换到 `book_key` 主键。

## Phase 2：搜索准确度与速度（P0，2-3 周）

1. 在 `backend/services/search.py` 建立统一结果模型（评分、去重 key、健康度、耗时统计）。
2. 实现搜索去重与折叠。
3. 引入源健康度（成功率、超时、异常、平均耗时）并进入排序。
4. 增加短 TTL 缓存和 `fast/full` 模式。
5. PWA 搜索页区分“快速结果”和“完整结果”。
6. 墨水屏端仅消费服务端优化后结果，不实现书源规则解析。
7. 补测试：去重、排序、降级、缓存命中、fast/full 语义。

## Phase 3：单容器任务层（P0，2-3 周）

1. 建立 SQLite-backed 任务模型（id/type/status/progress/error/timestamps）。
2. 把 `/api/offline/tasks` 切到“创建任务 + 返回任务信息”语义。
3. 增加同进程后台执行与状态轮询；不支持 worker 时显式失败或禁用。
4. `/api/offline/catalog` 改为读取任务结果和缓存状态汇总。
5. 为后续音频任务预留任务类型。
6. 补测试：任务创建、轮询、成功/失败、幂等、缓存落库。

## Phase 4：PWA 阅读体验（P1，1-2 周）

1. 阅读页实现自动翻页（开始、暂停、继续、章节切换自动暂停）。
2. 自动翻页与用户操作互斥：手动滚动、目录跳转、设置面板、离开页面时暂停。
3. `sync-queue` 以 `user_id + book_key` 去重，同书只保留最后进度。
4. 搜索页接入 `fast/full` 行为。
5. 前端验收：章节缓存命中、自动翻页、离线补传、搜索两种模式。

## Phase 5：墨水屏客户端闭环（P1，2-3 周）

1. API DTO 对齐新契约，`book_key` 设为必需字段。
2. 阅读路径保持本地章节优先，未缓存章节只给静态提示和显式下载入口。
3. 本地缓存与待同步队列按 `book_key` 收敛，只保留最后进度。
4. 离线下载改为显式创建任务并轮询状态。
5. 实现自动翻页、刷新策略和实体按键预留入口。
6. 冲突返回 `conflict=true` 时不直接覆盖本地状态。
7. Android 验收：Debug/Release 构建通过，弱网与补传行为正确。

## Phase 6：有声书最小能力（P1/P2，Phase 3 后）

1. 服务端复用任务层提供音频任务、缓存状态、流式/下载接口。
2. PWA 提供最小播放器（播放、暂停、章节切换、进度记忆）。
3. 墨水屏端只接已生成音频与最小播放控制。
4. 禁止把音频逻辑塞入正文章节接口。

## 阶段验收命令

后端测试：

```bash
./.venv/bin/python -m pytest tests/
```

前端构建：

```bash
cd frontend && npm run build
```

Docker 单容器构建：

```bash
docker build -t easyreader .
```

Android Debug：

```bash
cd e-link-client && JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest :app:assembleDebug --no-daemon
```

Android Release：

```bash
cd e-link-client && JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:assembleRelease --no-daemon
```

## 持续维护约束

- 新增接口先更新 `docs/client-server-contract.md` 再落代码。
- 新阶段目标先更新本执行计划再推进实现。
- 任何文档变更都不得把“未实现能力”写成“已落地能力”。