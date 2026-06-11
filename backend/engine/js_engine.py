"""QuickJS sandbox with full HTTP bridge.

Two modes:
1. Legado snippet: execute(@js: ...) with result variable
2. Tauri full source: load JS file, call search()/chapterContent() etc.
"""

import base64
import hashlib
import json
import logging
import re

import httpx
import quickjs

from backend.config import settings

logger = logging.getLogger(__name__)


CF_PROXY = "https://tv.rio.edu.kg/reader-proxy"


def _sync_http_get(url: str, headers_json: str = "{}") -> str:
    """Synchronous HTTP GET — uses curl_cffi to bypass Cloudflare."""
    try:
        from curl_cffi import requests as cf_requests
        headers = json.loads(headers_json) if headers_json else {}
        from urllib.parse import urlparse
        parsed = urlparse(url)
        headers.setdefault("Referer", f"{parsed.scheme}://{parsed.netloc}/")
        headers.setdefault("User-Agent", settings.user_agent)
        r = cf_requests.get(url, headers=headers, impersonate="chrome120", timeout=20)
        return r.text
    except Exception as e:
        logger.debug(f"JS getText failed: {url} - {e}")
        # Fallback to CF proxy
        try:
            from urllib.parse import urlencode
            params = {"url": url}
            proxy_url = f"{CF_PROXY}?{urlencode(params)}"
            r = httpx.get(proxy_url, timeout=20, follow_redirects=True)
            return r.text
        except Exception:
            return ""


def _sync_http_post(url: str, body: str = "", headers_json: str = "{}") -> str:
    """Synchronous HTTP POST — called from QuickJS bridge."""
    try:
        headers = json.loads(headers_json) if headers_json else {}
        headers.setdefault("User-Agent", settings.user_agent)
        r = httpx.post(url, content=body, headers=headers, timeout=15, follow_redirects=True)
        return r.text
    except Exception as e:
        logger.debug(f"JS postText failed: {url} - {e}")
        return ""


def _aes_base64_decode_to_string(ciphertext: str, key: str, transformation: str = "", iv: str = "") -> str:
    """Decode common Legado Java AES helper calls."""
    if not isinstance(ciphertext, str) or not isinstance(key, str):
        return ""
    try:
        from Crypto.Cipher import AES

        raw = base64.b64decode(ciphertext)
        mode_name = (transformation or "").upper()
        if "CBC" in mode_name:
            cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, (iv or "").encode("utf-8"))
        elif "ECB" in mode_name:
            cipher = AES.new(key.encode("utf-8"), AES.MODE_ECB)
        else:
            cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, (iv or "").encode("utf-8"))

        decrypted = cipher.decrypt(raw)
        if decrypted:
            padding = decrypted[-1]
            if 0 < padding <= AES.block_size and decrypted.endswith(bytes([padding]) * padding):
                decrypted = decrypted[:-padding]
        return decrypted.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.debug(f"JS AES decode failed: {e}")
        return ""


class JSEngine:
    """QuickJS engine for Legado @js: snippets."""

    def __init__(self):
        self._context: quickjs.Context | None = None

    def _get_context(self) -> quickjs.Context:
        if self._context is None:
            self._context = quickjs.Context()
            self._inject_bridge(self._context)
        return self._context

    def _inject_bridge(self, ctx: quickjs.Context):
        bridge_js = """
        var result = "";
        var baseUrl = "";
        var key = "";
        var page = 1;
        var keyword = "";

        var java = {
            ajax: function(url) { return __getText(url, "{}"); },
            get: function(url) { return __getText(url, "{}"); },
            post: function(url, body, headers) { return __postText(url, body || "", JSON.stringify(headers || {})); },
            base64Encode: function(str) { return __base64Encode(str); },
            base64Decode: function(str) { return __base64Decode(str); },
            md5Encode: function(str) { return __md5Encode(str); },
            aesBase64DecodeToString: function(str, key, transformation, iv) {
                return __aesBase64DecodeToString(str, key || "", transformation || "", iv || "");
            },
            log: function(msg) { __log(String(msg)); },
            put: function(key, value) {},
        };
        """
        ctx.eval(bridge_js)

        ctx.add_callable("__getText", _sync_http_get)
        ctx.add_callable("__postText", _sync_http_post)
        ctx.add_callable("__base64Encode", lambda s: base64.b64encode(s.encode()).decode() if isinstance(s, str) else "")
        ctx.add_callable("__base64Decode", lambda s: base64.b64decode(s).decode() if isinstance(s, str) else "")
        ctx.add_callable("__md5Encode", lambda s: hashlib.md5(s.encode()).hexdigest() if isinstance(s, str) else "")
        ctx.add_callable("__aesBase64DecodeToString", _aes_base64_decode_to_string)
        ctx.add_callable("__log", lambda msg: logger.debug(f"JS: {msg}"))

    def execute(self, script: str, result: str = "", **variables) -> str:
        ctx = self._get_context()

        ctx.eval(f"result = {json.dumps(result or '')};")
        for k, v in variables.items():
            ctx.eval(f"{k} = {json.dumps(str(v))};")

        script = script.strip()
        if script.startswith("<js>"):
            script = script[4:]
        if script.endswith("</js>"):
            script = script[:-5]
        if script.startswith("@js:"):
            script = script[4:]
        script = script.strip()

        try:
            val = ctx.eval(script)
            if val is None:
                return ""
            return str(val)
        except Exception as e:
            logger.debug(f"JS eval error: {e}")
            return ""

    def reset(self):
        self._context = None


class TauriEngine:
    """Execute Legado Tauri JS source files."""

    def __init__(self, source_code: str, source_url: str = ""):
        self._source_code = self._preprocess(source_code)
        self._source_url = source_url
        self._ctx: quickjs.Context | None = None

    def _preprocess(self, code: str) -> str:
        """Strip async/await so QuickJS can run it synchronously."""
        code = re.sub(r'\basync\s+function\b', 'function', code)
        code = re.sub(r'\bawait\s+', '', code)
        return code

    def _get_context(self) -> quickjs.Context:
        if self._ctx is None:
            self._ctx = quickjs.Context()
            # Memory limit: 32MB per source to prevent OOM
            try:
                self._ctx.set_memory_limit(32 * 1024 * 1024)
            except AttributeError:
                pass  # Older quickjs versions may not support this
            self._inject_bridge()
            self._load_source()
        return self._ctx

    def _inject_bridge(self):
        ctx = self._ctx

        # DOM store for parsed documents
        self._dom_store: dict[int, "BeautifulSoup"] = {}
        self._dom_counter = 0

        def dom_parse(html: str) -> int:
            from bs4 import BeautifulSoup
            self._dom_counter += 1
            self._dom_store[self._dom_counter] = BeautifulSoup(html, "lxml")
            return self._dom_counter

        def dom_free(doc_id: int) -> str:
            self._dom_store.pop(int(doc_id), None)
            return ""

        def dom_select_all(doc_id: int, selector: str) -> str:
            doc = self._dom_store.get(int(doc_id))
            if not doc:
                return "[]"
            elements = doc.select(selector)
            ids = []
            for el in elements:
                self._dom_counter += 1
                self._dom_store[self._dom_counter] = el
                ids.append(self._dom_counter)
            return json.dumps(ids)

        def dom_select(doc_id: int, selector: str) -> int:
            doc = self._dom_store.get(int(doc_id))
            if not doc:
                return 0
            el = doc.select_one(selector)
            if not el:
                return 0
            self._dom_counter += 1
            self._dom_store[self._dom_counter] = el
            return self._dom_counter

        def dom_select_text(doc_id: int, selector: str) -> str:
            doc = self._dom_store.get(int(doc_id))
            if not doc:
                return ""
            el = doc.select_one(selector)
            return el.get_text(strip=True) if el else ""

        def dom_select_attr(doc_id: int, selector: str, attr: str) -> str:
            doc = self._dom_store.get(int(doc_id))
            if not doc:
                return ""
            el = doc.select_one(selector)
            return el.get(attr, "") if el else ""

        def dom_attr(doc_id, attr: str) -> str:
            try:
                did = int(doc_id)
            except (TypeError, ValueError):
                return ""
            doc = self._dom_store.get(did)
            if not doc:
                return ""
            if hasattr(doc, "get"):
                val = doc.get(attr, "")
                return val if isinstance(val, str) else ""
            return ""

        bridge_js = """
        function getText(url, headers) {
            return __getText(url, JSON.stringify(headers || {}));
        }
        function postText(url, body, headers) {
            return __postText(url, body || "", JSON.stringify(headers || {}));
        }
        function getJson(url, headers) {
            var t = getText(url, headers);
            try { return JSON.parse(t); } catch(e) { return null; }
        }
        function log(msg) { __log(String(msg)); }

        var legado = {
            http: {
                get: function(url, headers) { return __getText(url, JSON.stringify(headers || {})); },
                post: function(url, body, headers) { return __postText(url, body || "", JSON.stringify(headers || {})); }
            },
            dom: {
                parse: function(html) { return __domParse(html); },
                free: function(docId) { __domFree(docId); },
                selectAll: function(docId, selector) { return JSON.parse(__domSelectAll(docId, selector)); },
                select: function(docId, selector) { return __domSelect(docId, selector); },
                selectText: function(docId, selector) { return __domSelectText(docId, selector); },
                selectAttr: function(docId, selector, attr) { return __domSelectAttr(docId, selector, attr); },
                attr: function(docId, attr) { return __domAttr(docId, attr); }
            },
            log: function(msg) { __log(String(msg)); },
            sleep: function(ms) {},
            toast: function(msg) { __log(String(msg)); },
            browser: {
                acquire: function() { return 0; },
                navigate: function() {},
                html: function() { return ""; },
                show: function() {},
                hide: function() {},
                cookies: function() {}
            }
        };
        """
        ctx.eval(bridge_js)

        ctx.add_callable("__getText", _sync_http_get)
        ctx.add_callable("__postText", _sync_http_post)
        ctx.add_callable("__log", lambda msg: logger.debug(f"Tauri: {msg}"))
        ctx.add_callable("__domParse", dom_parse)
        ctx.add_callable("__domFree", dom_free)
        ctx.add_callable("__domSelectAll", dom_select_all)
        ctx.add_callable("__domSelect", dom_select)
        ctx.add_callable("__domSelectText", dom_select_text)
        ctx.add_callable("__domSelectAttr", dom_select_attr)
        ctx.add_callable("__domAttr", dom_attr)

    def _load_source(self):
        try:
            self._ctx.eval(self._source_code)
        except Exception as e:
            logger.warning(f"Tauri source load error: {e}")

    def call(self, func_name: str, *args) -> str:
        """Call a function in the source and return JSON string result."""
        ctx = self._get_context()
        args_json = ", ".join(json.dumps(a) for a in args)
        call_expr = f"JSON.stringify({func_name}({args_json}))"
        try:
            result = ctx.eval(call_expr)
            return result if result else "[]"
        except Exception as e:
            logger.warning(f"Tauri call {func_name} error: {e}")
            return "[]"

    def search(self, keyword: str, page: int = 1) -> list[dict]:
        result = self.call("search", keyword, page)
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return []

    def book_info(self, book_url: str) -> dict | None:
        result = self.call("bookInfo", book_url)
        try:
            data = json.loads(result)
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None

    def chapter_list(self, book_url: str) -> list[dict]:
        result = self.call("chapterList", book_url)
        try:
            data = json.loads(result)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def chapter_content(self, chapter_url: str) -> str:
        result = self.call("chapterContent", chapter_url)
        try:
            data = json.loads(result)
            if isinstance(data, list):
                return json.dumps(data)
            return str(data) if data else ""
        except (json.JSONDecodeError, TypeError):
            return result or ""


def parse_tauri_metadata(source_code: str) -> dict:
    """Parse @name, @url, @type etc. from JS header comments."""
    meta = {}
    for line in source_code.split("\n")[:30]:
        line = line.strip()
        if not line.startswith("//"):
            if line and not line.startswith("/*"):
                break
            continue
        m = re.match(r'//\s*@(\w+)\s+(.+)', line)
        if m:
            meta[m.group(1)] = m.group(2).strip()
    return meta


# --- Legacy API (used by existing Legado rule engine) ---

_engine = JSEngine()


def execute(rule: str, content: str = "", **variables) -> str:
    return _engine.execute(rule, result=content, **variables)


def reset():
    _engine.reset()
