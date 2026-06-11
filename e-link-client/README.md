# E-link Client

Dedicated Android client workspace for e-ink reading devices.
All client-specific code lives under this directory only.

## What is implemented
- Independent Android app scaffold (Kotlin + Jetpack Compose)
- Android 8.1 Go+ compatibility baseline (minSdk 27)
- No Google Play Services / Firebase dependency
- E-ink style high-contrast UI baseline
- PWA-aligned page structure (default landing on bookshelf):
	- `书架` / `搜索` / `阅读` / `设置`
- Chapter-first local reader baseline for novel content
- Device-level e-ink refresh policy baseline:
	- `Speed` / `Balanced` / `Quality`
	- Full refresh every N page turns (mode-based)
	- Vendor API bridge with safe fallback invalidate
- Server sync integration:
	- `POST /api/sync/progress/upsert`
	- `GET /api/sync/progress/pull`
- Server-task-backed offline pipeline integration:
	- Search triggered on server via SSE `/api/search`
	- Add to server bookshelf via `POST /api/books`
	- Trigger server cache task via `POST /api/offline/tasks`
	- Download and persist chapter cache to client local storage
	- Local chapter read path consumes client cache only; uncached chapters show static guidance
- Performance optimizations for e-ink and low-end devices:
	- Target profile tuned for Android Go class low-RAM devices
	- HTTP response cache enabled in OkHttp
	- HTTP wire logging disabled by default
	- Local offline caching progress callbacks are throttled to reduce UI recomposition
	- Background progress sync avoids global loading flicker
	- Reader chapter shortcuts and full-refresh overlay are reduced on low-RAM devices
- Offline integration APIs:
	- `GET /api/offline/catalog`
	- `POST /api/offline/tasks`
- Settings page actions:
	- Server config (`base_url`, `user_id`)
	- Manual progress sync
	- Manual pull remote progress
	- Manual pull server bookshelf
	- Clear client local cache

## Directory layout
```
e-link-client/
	app/
		src/main/java/com/easyreader/elinkclient/
			core/
			data/
			ui/
		src/main/res/
	docs/
		eink-client-plan.md
	build.gradle.kts
	settings.gradle.kts
```

## Documentation
- Client architecture: `docs/eink-client-plan.md`
- Current phase scope and next steps: `../docs/phase1.md`

## Run in Android Studio
1. Open Android Studio and choose `Open`.
2. Select `EasyReader/e-link-client`.
3. Let Gradle sync complete.
4. Run app on an emulator/device.

## Server connection
- Default base URL is `http://10.0.2.2:8000/` (Android emulator to host mapping).
- On physical device, change base URL in `设置` tab to your LAN IP,
	for example `http://192.168.1.20:8000/`.

## Current baseline constraints
- Manga chapter rendering is URL-placeholder baseline in v1.
- Local cache uses file-based store in app sandbox (not Room yet).
- Request header injection and sync conflict response handling are not fully aligned with the current backend contract yet.
- Offline flow still needs an explicit task-state UI instead of a foreground blocking chain.
- Hardware key mapping is not implemented yet.
- Vendor-specific e-ink refresh APIs are best-effort reflection bridge; fallback is standard view invalidate.

## Next milestones
- Inject client headers and contract version at the network layer
- Handle sync conflict fields explicitly in Android DTO/state flow
- Split offline flow into explicit task-state UI and local-persist phases
- Hardware key/tap-zone customization
- Deep vendor refresh SDK integration per device family
