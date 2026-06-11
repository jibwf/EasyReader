# EasyReader 多端边界与 API 契约

更新时间：2026-06-11

## 文档目的

这份文档只回答三件事：

- 当前服务端真正对外提供了什么能力。
- Web PWA 和墨水屏客户端各自应该负责什么，不应该负责什么。
- 现阶段 API 的真实字段、同步语义和已知边界是什么。

它不是产品愿景文档，也不是未来功能清单。凡是这里写的，默认都要能在当前仓库代码里找到对应实现。

## 当前结论

- 服务端已经是多客户端共享后端，但还不是“统一账号系统”的成品。
- Web 端当前是可安装的 PWA，定位是混合在线优先客户端。
- 墨水屏端定位是本地阅读优先客户端，应该使用比 PWA 更收敛的联网策略。
- 服务端对共享状态是权威源，但并不管理客户端的细粒度 UI 状态。
- 当前 API 是 MVP 可用基线，不是长期最佳实践；后续应优先重构搜索、任务层、资源身份和同步幂等性。
- RSS 和漫画暂时不进入下一阶段路线；账号 / 鉴权保持低优先级。

## 身份与版本基线

### 当前身份模型

- 当前没有登录、鉴权、用户会话或服务端分发账号体系。
- `user_id` 由客户端自己提供。
- `device_id` 也由客户端自己生成并持久化。
- Web PWA 当前默认把 `user_id` 初始化为 `demo-user`，再保存在本地浏览器。

这意味着：

- 当前“多端同步”本质上依赖多个客户端主动使用同一个 `user_id`。
- 这是一套开发期/单用户自托管基线，不应被文档表述成“已完成的统一账号系统”。

### 版本与客户端类型

当前服务端会在所有 `/api/*` 响应头里返回：

- `X-Server-Version`
- `X-API-Contract-Version`
- `X-Supported-Client-Types`

当前 Web PWA 会在所有 API 请求头里带上：

- `X-Client-Type: web-pwa`
- `X-Client-Version`
- `X-API-Contract-Version`

墨水屏客户端后续应对齐同一约定，建议使用：

- `X-Client-Type: eink-android`
- `X-Client-Version: <客户端版本>`
- `X-API-Contract-Version: 2026-06-11`

## 服务端与客户端处理边界

| 领域 | 服务端负责 | Web PWA 负责 | 墨水屏客户端负责 |
| --- | --- | --- | --- |
| 书源解析 | 搜索、详情抓取、目录解析、正文抓取、数据清洗 | 不解析规则，调用 API 展示结果 | 不解析规则，调用 API 或本地缓存结果 |
| 书架主数据 | `books`、分类、服务端缓存统计 | 书架展示、分类操作、批量操作入口 | 书架精简展示、最近阅读、离线入口 |
| 正文章节 | 提供目录和章节正文接口，维护服务端章节缓存 | 在线阅读、预取后续章节、浏览器缓存 | 本地章节阅读、显式下载、未缓存提示 |
| 共享进度 | 存储跨端共享的章节进度、冲突判断、revision | 上报阅读进度、按书去重的补传失败队列 | 上报章节进度、按书去重后在 WiFi 恢复时补传 |
| 书签 | 存储共享书签与 revision | 批量上报/拉取书签 | 后续可选接入，不要求首版必须实现 |
| 离线任务 | 生成离线任务结果、维护离线目录 | 触发任务，并把章节写入浏览器 IndexedDB | 触发任务，只把结果当“允许下载/已缓存目录”来源 |
| 字体资源 | 列出服务器字体、提供字体下载 | 选择或应用本地字体策略 | 下载、缓存、启用设备字体 |
| UI 与设备交互 | 不负责 | 页面布局、浏览器缓存、PWA 安装体验 | 墨水屏刷新、实体按键、热区、低功耗交互 |

边界原则：

- 服务端输出可复用数据和共享状态，不输出客户端 UI 状态机。
- 客户端负责阅读体验，不负责书源规则执行。
- PWA 可以是混合在线优先；墨水屏客户端必须是阅读路径本地优先。

## API 设计基线

### 通用约定

- 当前 API 直接返回 JSON 模型，不使用统一 `{ code, message, data }` 包装。
- 时间字段当前来自 SQLite `datetime('now')`，格式为 `YYYY-MM-DD HH:MM:SS`，按 UTC 解释。
- `/api/*` 默认返回 `Cache-Control: no-store`；PWA 的离线能力主要依赖 Workbox Cache Storage 和 IndexedDB，而不是浏览器默认 HTTP 缓存。

### 版本与能力查询

#### `GET /api/version`

返回：

```json
{
  "version": "202606101",
  "api_contract_version": "2026-06-11",
  "supported_client_types": ["web-pwa", "eink-android"]
}
```

用途：

- PWA 版本刷新。
- 客户端判断自己是否在受支持名单内。
- 文档和代码对齐当前 API 契约版本。

### 书架与内容

#### `GET /api/books`

当前用于书架列表展示，支持：

- `include_hidden`
- `category`

返回书籍字段基线：

- `id`
- `name`
- `author`
- `cover_url`
- `intro`
- `book_url`
- `source_url`
- `category_name`
- `last_chapter`
- `total_chapters`
- `added_at`
- `updated_at`

#### `GET /api/content/book-info`

查询参数：

- `book_url`
- `source_url`

返回单本书详情。

#### `GET /api/content/chapters`

查询参数：

- `book_url`
- `source_url`

返回目录数组，字段基线：

- `id`
- `book_id`
- `title`
- `url`
- `idx`
- `cached`

#### `GET /api/content/chapter`

查询参数：

- `url`
- `source_url`

返回两种内容模型之一：

小说：

```json
{ "type": "novel", "content": "...", "images": [] }
```

漫画兼容响应：

```json
{ "type": "manga", "content": "", "images": ["https://..."] }
```

约定：

- 服务端负责把正文归一成文本或图片列表。
- 客户端负责真正的阅读器渲染方式。
- 当前代码仍可能识别漫画型正文，但漫画不再作为下一阶段产品路线和验收重点。

### 当前 API 非最佳实践点

这些问题不影响 MVP 运行，但会影响服务端作为“共享内容与共享状态中心”的长期稳定性：

- 搜索结果按书源返回顺序流式推送，缺少全局评分、去重、源健康度、短 TTL 缓存和快速/完整模式。
- 书架命中会优先返回，远端搜索体验需要继续优化，避免用户想找新书时被本地结果截断。
- 内容资源身份仍依赖 `book_url + source_url`，需要稳定 `book_key` 或 `book_id` 作为客户端主键。
- 进度同步主键当前以 `(user_id, book_url)` 为核心，后续应纳入 `source_url` 或直接使用 `book_key`。
- 离线任务接口当前在请求内同步执行，后续应迁移到真正任务层。
- 错误响应、缓存语义和 revision 生成策略需要统一。

推荐重构详见 [docs/next-stage-execution-plan.md](./next-stage-execution-plan.md)。

### 兼容进度接口

#### `POST /api/progress`

当前仍保留旧接口，字段包括：

- `book_url`
- `source_url`
- `book_name`
- `chapter_idx`
- `chapter_title`
- `chapter_url`
- `scroll_percent`

#### `GET /api/progress`

返回最近 20 条旧版阅读进度。

#### `GET /api/progress/{book_url}`

返回某本书的旧版阅读进度。

这组接口当前仅作为兼容兜底，不应再扩展新语义。

### 同步进度接口

#### `POST /api/sync/progress/upsert`

请求字段：

- `user_id`
- `device_id`
- `book_url`
- `source_url`
- `book_name`
- `chapter_idx`
- `chapter_title`
- `chapter_url`
- `position`
- `force`

响应字段：

- 上述主体字段
- `revision`
- `updated_at`
- `accepted`
- `conflict`
- `conflict_reason`

冲突语义：

- 如果新进度章节回退，返回 `chapter_regression`。
- 如果同章位置明显回退，返回 `position_regression`。
- `force=true` 可以覆盖冲突。

#### `GET /api/sync/progress/pull`

查询参数：

- `user_id`
- `since`
- `limit`

返回：

```json
{
  "items": [SyncProgressItem],
  "next_cursor": 12
}
```

约定：

- `revision` 是当前增量同步游标。
- 服务端以 `(user_id, book_url)` 为唯一共享进度键。
- 当前还没有按账号、书源隔离的复杂权限模型。

### 书签同步接口

#### `POST /api/sync/bookmarks/batch`

请求字段：

- `user_id`
- `device_id`
- `items[]`

单个 `items[]` 元素字段：

- `bookmark_id`
- `book_url`
- `source_url`
- `book_name`
- `chapter_idx`
- `chapter_title`
- `chapter_url`
- `position`
- `quote_text`
- `note`
- `deleted`

#### `GET /api/sync/bookmarks/pull`

查询参数：

- `user_id`
- `since`
- `limit`

返回与进度同步同样的游标模型。

### 离线任务接口

#### `POST /api/offline/tasks`

请求字段：

- `user_id`
- `device_id`
- `book_id` 或 `book_url + source_url`

响应字段：

- `task_id`
- `user_id`
- `device_id`
- `book_id`
- `book_name`
- `book_url`
- `source_url`
- `status`
- `total_chapters`
- `cached_chapters`
- `error_message`
- `created_at`
- `updated_at`
- `completed_at`

当前语义必须注意：

- 这不是完整后台任务队列。
- 当前实现会在请求期间直接执行服务端缓存流程，然后返回最终结果。
- `queued` / `running` 目前更多是状态字段兼容，而不是长期轮询协议承诺。

#### `GET /api/offline/tasks/{task_id}`

获取单个离线任务结果。

#### `GET /api/offline/tasks`

查询参数：

- `user_id`
- `device_id`
- `limit`

返回某设备的离线任务列表。

#### `GET /api/offline/catalog`

查询参数：

- `user_id`
- `device_id`

返回当前设备的离线目录摘要：

- `user_id`
- `device_id`
- `book_id`
- `book_url`
- `source_url`
- `name`
- `author`
- `total_chapters`
- `cached_chapters`
- `updated_at`

### 字体接口

#### `GET /api/fonts`

返回服务端字体列表。

#### `GET /api/fonts/{font_file_name}/download`

返回字体文件下载流。

## Web PWA 行为契约

当前 PWA 不是纯离线客户端，也不是纯服务端渲染前端，而是混合在线优先客户端：

- 书架、离线目录、离线任务列表会优先请求服务端，失败时回退本地 localStorage 快照。
- 目录元数据会写入 localStorage。
- 章节正文会写入 IndexedDB。
- Workbox 还会对书架、目录、章节和同步拉取接口做运行时缓存。
- 阅读器命中本地章节缓存时会先展示本地内容，但仍会尝试联网刷新正文。
- 阅读中会自动预取后续 3 章。
- 进度补传队列会按 `user_id + book_url + source_url` 去重，同一本书只保留最后一条待同步进度。

这意味着：

- PWA 适合手机或普通浏览器阅读。
- 它不是墨水屏端的直接行为模板。

## 墨水屏客户端行为契约

墨水屏端不应复制 PWA 的在线优先策略，而应使用更收敛的客户端契约：

- 阅读路径只读本地缓存章节。
- 目录和章节下载必须是显式动作。
- 自动同步只限阅读进度，不包含章节正文拉取。
- WiFi 不可用时应只保留本地阅读和待同步队列。
- 待同步队列应按书收敛，只保留最后一次有效阅读位置，而不是缓存一串已经过时的章节进度。

墨水屏客户端与当前服务端最小对接面建议保留为：

- `/api/version`
- `/api/books`
- `/api/content/chapters`
- `/api/content/chapter`
- `/api/sync/progress/upsert`
- `/api/sync/progress/pull`
- `/api/offline/tasks`
- `/api/offline/catalog`
- `/api/fonts`
- `/api/fonts/{font_file_name}/download`

## 当前已知缺口

- 还没有统一账号体系，`user_id` 仍由客户端自管。
- 还没有真正异步的后台离线任务队列。
- 还没有把客户端能力协商做成正式 capability endpoint。
- 还没有把 PWA 和墨水屏端在“联网策略”层彻底拆开。

这些都应该被记录为下一阶段工作，而不是写成“当前已完成能力”。