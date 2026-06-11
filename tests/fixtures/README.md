# Source Compatibility Fixtures

These fixtures are offline compatibility baselines for common book source shapes.

Rules:

- Keep fixtures deterministic. Do not call public book source sites from tests.
- Each Legado case should cover search, chapter list, and chapter content.
- Add a new case when a real source exposes a new rule pattern, not for cosmetic HTML differences.
- Prefer small synthetic payloads that preserve the failing structure from the real source.

Current coverage:

- `html-css-novel`: CSS/JSOUP selectors, relative URLs, paginated chapter content.
- `json-api-source`: JSONPath search, JSONPath TOC, JSONPath chapter body.
- `json-manga-image-list`: JSONPath manga source where chapter content is an image URL list.
- `xpath-relative-source`: XPath result nodes with relative element rules such as `.//a/text()` and `./@href`.
- `TAURI_SOURCE`: Legado Tauri JavaScript source metadata, search, chapter list, and image-list content.

Real-source replay:

Use `scripts/replay_source.py` when a source is reachable in the current network and already imported in `data/reader.db`.

```bash
python scripts/replay_source.py --keyword 三体 --source-name 源名称片段
python scripts/replay_source.py --keyword 三体 --source-url https://example.com/source
```

The script writes raw fetched responses plus a `manifest.json` into `tests/fixtures/replays/`.
Review the snapshot before committing. Cookies and authorization headers are redacted, but response bodies may still contain site-specific or user-specific data.

Batch smoke:

Use `scripts/smoke_sources.py` to quickly rank imported sources before creating detailed replays.

```bash
python scripts/smoke_sources.py --keyword 三体 --limit 20
python scripts/smoke_sources.py --keyword 三体 --source-name 笔趣阁 --format json --output /tmp/reader-smoke.json
```

Smoke reports should normally stay outside the repository unless converted into a minimal deterministic fixture.
