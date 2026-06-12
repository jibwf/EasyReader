# EasyReader

EasyReader 是一个自托管、多端阅读系统，目标是把在线书源、本地书籍、阅读进度、离线缓存和多客户端同步收敛到一个可长期维护的个人阅读平台。

项目现在按独立产品线维护，后续路线围绕服务端核心能力、搜索质量、客户端阅读体验和有声书任务体系持续演进。

## 致谢与来源说明

EasyReader 的早期形态参考并继承了 [qq148376839/reader](https://github.com/qq148376839/reader) 的大量工作，包括阅读器基础能力、书源处理思路、内容抓取流程和部分工程实现。感谢原作者 `qq148376839` 以及相关社区积累，让这个项目有了可以继续演进的基础。 

当前 EasyReader 已经围绕自托管、多端同步、PWA 离线能力、服务端缓存、本地书籍管理和墨水屏客户端方向进行了持续重构。后续维护目标是独立演进这个项目，而不是作为对原项目的补丁分支；

## 当前定位

EasyReader 当前由三部分组成：

- FastAPI 共享服务端：负责书源解析、内容抓取、书架主数据、章节缓存、同步状态、离线任务和字体资源。
- React + Vite Web PWA：面向浏览器和移动端主屏安装，采用在线优先 + 本地缓存增强的阅读体验。
- Kotlin Android 墨水屏客户端：面向低刷新、低干扰、本地阅读优先的设备体验，独立维护在 `e-link-client/`。

当前产品边界很明确：服务端是共享内容与状态中心，Web PWA 是通用阅读客户端，墨水屏客户端是本地阅读优先客户端。三端共享 API 契约，但不强迫采用同一种联网策略。

## 核心能力

### 书源与内容

- 导入、启用、禁用和删除书源。
- 多源搜索与书籍发现。
- 获取书籍详情、目录和章节正文。
- 支持在线小说正文阅读。
- 服务端章节缓存，降低重复抓取成本。

### 本地书籍

- 导入 `JSON`、`TXT`、`EPUB`。
- 本地导入书籍可直接进入阅读。
- EPUB 章节标题清洗，避免出现 `Text/...xhtml` 这类不友好的目录名。
- 批量删除、批量预缓存、批量导出 `TXT` / `EPUB`。

### 书架与阅读

- 书架列表、分类、隐藏和批量管理。
- 继续阅读进度。
- 阅读中预取后续章节。
- 服务端与浏览器两层缓存统计和清理。
- 浏览器 IndexedDB 章节缓存。
- PWA Workbox 运行时缓存。

### 多端同步

- 进度同步：`POST /api/sync/progress/upsert`、`GET /api/sync/progress/pull`。
- 书签同步：`POST /api/sync/bookmarks/batch`、`GET /api/sync/bookmarks/pull`。
- 离线目录：`POST /api/offline/tasks`、`GET /api/offline/catalog`。
- 服务端字体清单与字体下载接口，供客户端复用。
- API 版本与客户端契约头，便于 Web PWA 和墨水屏客户端对齐能力边界。
- 服务端备份下载与恢复上传，支持全量恢复或增量恢复冲突处理。

## 架构概览

当前部署形态是单容器部署：

- 前端在 Docker 构建阶段打包为静态文件。
- FastAPI 在运行时同时提供 `/api/*` 和前端 SPA 回退。
- 运行期数据全部写入 `data/` volume。
- 容器启动时会准备运行所需的数据目录和字体目录。

```text
Browser / PWA      ->  FastAPI  -> SQLite
E-link Android     ->  FastAPI  -> data/cache
                                -> data/exports
                                -> data/fonts
```

更详细的架构、阶段状态和客户端说明见：

- [docs/README.md](docs/README.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/phase1.md](docs/phase1.md)
- [e-link-client/docs/eink-client-plan.md](e-link-client/docs/eink-client-plan.md)

## 开发协作说明

- 当前仓库不再使用 Claude 工作流。
- 后续开发统一以仓库文档（`docs/`）和 `.copilot-instructions.md` 作为 AI 协作基线。

## 技术栈

- 后端：FastAPI, aiosqlite, Pydantic, BeautifulSoup
- 前端：React, TypeScript, Vite, Zustand
- PWA：vite-plugin-pwa, Workbox, idb-keyval
- 本地文件：EbookLib, python-multipart
- 墨水屏客户端：Kotlin / Android
- 数据库：SQLite
- 部署：单容器 Docker

## 目录结构

```text
EasyReader/
├── backend/       # FastAPI API、数据库、规则引擎和业务服务
├── frontend/      # React + Vite Web PWA
├── e-link-client/ # 墨水屏 Android 客户端
├── data/          # SQLite、缓存、导出文件和字体文件
├── tests/         # 后端回归测试
├── docs/          # 架构、阶段和共享约束文档
└── Dockerfile     # 单容器构建入口
```

## 本地开发

### 后端

要求：Python 3.11+

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8080 --reload
```

### 前端

要求：Node.js 20+

```bash
cd frontend
npm install
npm run dev
```

默认开发地址：

- 后端：`http://127.0.0.1:8080`
- 前端：`http://127.0.0.1:5173`

## 环境变量配置

所有配置项均通过 `READER_` 前缀的环境变量设置，也可通过 `.env` 文件配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `READER_DATA_DIR` | `data` | 数据存储目录 |
| `READER_DB_PATH` | `{DATA_DIR}/reader.db` | SQLite 数据库路径 |
| `READER_CACHE_DIR` | `{DATA_DIR}/cache` | 缓存目录 |
| `READER_LOG_LEVEL` | `INFO` | 日志级别 |
| `READER_PROXY` | `None` | HTTP 代理地址 |
| `READER_REQUEST_TIMEOUT` | `15` | 请求超时时间（秒） |
| `READER_MAX_CONCURRENT_REQUESTS` | `10` | 最大并发请求数 |
| `READER_OFFLINE_TASK_WORKER_ENABLED` | `True` | 是否启用离线任务 Worker |
| `READER_PASSWORD` | `""` | 登录密码（空=禁用密码认证） |
| `READER_TOKEN_EXPIRY_DAYS` | `90` | 登录 Token 有效期（天） |
| `READER_MAX_UPLOAD_SIZE_MB` | `200` | 最大上传文件大小（MB） |
| `READER_CORS_ORIGINS` | `"*"` | 允许的 CORS 来源（逗号分隔） |
| `READER_USER_AGENT` | Chrome 120 UA | 请求 User-Agent |

## 认证配置

设置密码保护系统访问：

```bash
# 设置密码（环境变量）
READER_PASSWORD=your-secret-password

# 可选：设置 Token 有效期（默认 90 天）
READER_TOKEN_EXPIRY_DAYS=90
```

首次访问时需要输入密码，验证通过后 Token 保存在浏览器/客户端本地，90 天内无需重新输入。

## 测试与构建

后端测试：

```bash
.venv/bin/python -m pytest
```

前端构建：

```bash
cd frontend
npm run build
```

Docker 构建：

```bash
docker build -t easyreader .
```

Docker 运行：

```bash
docker run --rm -p 8080:8080 -v $(pwd)/data:/app/data easyreader
```

## 运行期数据

运行期数据默认存放在 `data/` 下：

- `reader.db`：SQLite 数据库。
- `cache/`：章节内容和运行缓存。
- `exports/`：批量导出的 TXT / EPUB 文件。
- `fonts/`：服务器字体文件目录，支持 `.ttf/.otf/.ttc/.woff/.woff2`。

## API 概览

当前核心 API 包括：

- `GET /api/version`：服务端版本、API 契约版本和支持的客户端类型。
- `GET /api/books`：获取书架列表。
- `POST /api/books/import`：导入 `JSON`、`TXT` 或 `EPUB`。
- `POST /api/books/delete-batch`：批量删除书籍。
- `POST /api/books/cache-batch`：批量预缓存章节。
- `POST /api/books/export-batch`：批量导出书籍。
- `GET /api/books/cache/stats`：查看服务端缓存统计。
- `POST /api/books/cache/clear`：清理服务端缓存。
- `GET /api/books/exports/{file_name}`：下载导出文件。
- `GET /api/content/book-info`：获取书籍详情。
- `GET /api/content/chapters`：获取目录。
- `GET /api/content/chapter`：获取章节正文。
- `POST /api/progress` / `GET /api/progress`：兼容旧版阅读进度。
- `POST /api/sync/progress/upsert` / `GET /api/sync/progress/pull`：多端进度同步。
- `POST /api/sync/bookmarks/batch` / `GET /api/sync/bookmarks/pull`：书签同步。
- `POST /api/offline/tasks` / `GET /api/offline/tasks` / `GET /api/offline/catalog`：离线任务与离线目录。
- `GET /api/fonts`：获取服务器字体列表。
- `GET /api/fonts/{font_file_name}/download`：下载服务器字体文件。
- `GET /api/backup/export`：下载服务端备份 ZIP。
- `POST /api/backup/restore`：上传备份 ZIP 并执行全量/增量恢复。

## 当前状态

已经完成的重点能力：

- 服务端资源身份、搜索排序、源健康度、同步幂等和离线任务层重构。
- 书架内一体化书籍管理，以及本地 `TXT` / `EPUB` 导入阅读。
- Web PWA 的 IndexedDB + Workbox 双层缓存、`fast/full` 搜索、自动翻页和冲突处理。
- 多端进度同步、书签同步、后台离线任务与离线目录 API。
- 墨水屏 Android 客户端的 `book_key` 基线、本地缓存阅读、WiFi 闸门和离线任务接入。
- 关键后端回归测试覆盖。

当前阶段主线：

- 墨水屏客户端补齐请求头、同步冲突处理和显式离线任务状态机。
- 阅读器设备交互收口，包括实体按键、缺章入口和刷新策略协同。
- 有声书 / 音频任务能力仍放在墨水屏客户端收口之后。

## 当前限制

- 还没有统一账号 / 鉴权系统；当前 `user_id` 与 `device_id` 仍由客户端自管。
- 还没有有声书 / 音频任务能力。
- Android 墨水屏客户端还没有完全补齐请求头、同步冲突语义和显式任务 UI。
- Web PWA 是在线优先 + 本地缓存增强客户端，不能直接等同于墨水屏客户端策略。
- RSS 和漫画暂时不进入下一阶段路线。

## 许可证

当前仓库尚未声明最终开源许可证。

在重新创建公开仓库前，建议先明确许可证策略：

- 如果作为私有自用项目，可以暂不添加开源许可证。
- 如果计划公开发布，需要补充 `LICENSE`，并确认仓库中保留的第三方代码、素材、工程结构和依赖说明符合对应授权要求。
- 如果保留了来自参考项目的代码或实现结构，需要继续保留“致谢与来源说明”，并按最终确认的许可证要求补充必要声明。
- 如果后续要接受外部贡献，建议同时补充贡献说明和版权归属约定。
