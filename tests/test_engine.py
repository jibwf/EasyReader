import json
import base64
import hashlib

from backend.engine import css_parser, jsonpath_parser, regex_parser, xpath_parser
from backend.engine.fetcher import parse_headers
from backend.engine.js_engine import execute as execute_js, reset as reset_js
from backend.engine.parser import RuleParser
from backend.engine.rule_chain import split_rules
from backend.engine.url_parser import make_absolute_url, parse_url


HTML = """
<html>
  <body>
    <section id="books">
      <article class="book" data-id="b1">
        <a class="title" href="/book/1">第一本书</a>
        <span class="author">作者甲</span>
        <p class="intro">简介 A</p>
      </article>
      <article class="book" data-id="b2">
        <a class="title" href="/book/2">第二本书</a>
        <span class="author">作者乙</span>
        <p class="intro">简介 B</p>
      </article>
    </section>
  </body>
</html>
"""


def test_css_parser_extracts_text_attributes_and_lists():
    assert css_parser.parse("@css:a.title", HTML) == ["第一本书", "第二本书"]
    assert css_parser.parse("@css:a.title@href", HTML) == ["/book/1", "/book/2"]

    books = css_parser.parse_list("@css:article.book", HTML)

    assert len(books) == 2
    assert css_parser.parse("@css:a.title", books[0]) == "第一本书"
    assert css_parser.parse("@css:article.book@data-id", HTML) == ["b1", "b2"]


def test_css_parser_supports_jsoup_index_pseudo_classes():
    assert css_parser.parse("@css:article.book:lt(1) a.title", HTML) == "第一本书"
    assert css_parser.parse("@css:article.book:eq(1) a.title", HTML) == "第二本书"
    assert css_parser.parse("@css:article.book:gt(0) a.title", HTML) == "第二本书"


def test_jsoup_shorthand_selects_elements_and_nested_values():
    books = css_parser.parse_list("class.book", HTML)

    assert len(books) == 2
    assert css_parser.parse("class.title@text", books[0]) == "第一本书"
    assert css_parser.parse("class.title@href", books[1]) == "/book/2"
    assert css_parser.parse("class.book.1@class.author@text", HTML) == "作者乙"


def test_jsoup_shorthand_reads_attribute_from_current_matching_tag():
    books = css_parser.parse_list("@css:article.book a.title", HTML)

    assert css_parser.parse("a@href", books[0]) == "/book/1"
    assert css_parser.parse("article.book a.title@href", HTML) == ["/book/1", "/book/2"]


def test_xpath_parser_extracts_text_and_attributes():
    assert xpath_parser.parse("//article[@class='book']/a/text()", HTML) == ["第一本书", "第二本书"]
    assert xpath_parser.parse("//article[@class='book'][1]/a/@href", HTML) == "/book/1"

    elements = xpath_parser.parse_list("//article[@class='book']", HTML)

    assert len(elements) == 2
    assert xpath_parser.get_element_text(elements[1], ".//span[@class='author']/text()") == "作者乙"


def test_jsonpath_parser_extracts_values_and_lists():
    payload = {
        "data": {
            "books": [
                {"name": "第一本书", "author": "作者甲"},
                {"name": "第二本书", "author": "作者乙"},
            ]
        }
    }

    assert jsonpath_parser.parse("$.data.books[*].name", payload) == ["第一本书", "第二本书"]
    assert jsonpath_parser.parse("$.data.books[0].author", json.dumps(payload)) == "作者甲"
    assert jsonpath_parser.parse_list("$.data.books[*]", payload) == payload["data"]["books"]
    assert jsonpath_parser.get_value(payload["data"]["books"][1], "$.name") == "第二本书"


def test_regex_parser_matches_groups_and_replacements():
    assert regex_parser.parse("##作者：(.*?)\\s", "作者：张三 最新章节") == "张三"
    assert regex_parser.parse("###(第)(一)(章)", "第一章 正文") == "第一章"
    assert regex_parser.parse("##\\s+##", "第一章   正文") == "第一章正文"
    assert regex_parser.parse("##[", "原文") == ""


def test_rule_parser_dispatches_inline_regex_and_compound_rules():
    parser = RuleParser()

    assert parser.parse("@css:a.title@href##/book/(\\d+)", HTML) == "1"
    assert parser.parse("@css:.missing || @css:a.title", HTML) == ["第一本书", "第二本书"]
    assert parser.parse("@css:a.title && @css:.author", HTML) == "第一本书\n第二本书\n作者甲\n作者乙"
    assert parser.parse("书名：${0}%%@css:a.title", HTML) == "书名：第一本书"
    assert split_rules("@css:a && @css:b") == ("&&", ["@css:a", "@css:b"])


def test_parse_element_supports_dict_html_and_xpath_elements():
    parser = RuleParser()

    assert parser.parse_element("$.name", {"name": "第一本书"}) == "第一本书"
    assert parser.parse_element("name", {"name": "第一本书"}) == "第一本书"

    elements = xpath_parser.parse_list("//article[@class='book']", HTML)
    assert parser.parse_element(".//a/text()", elements[0]) == "第一本书"


def test_url_parser_handles_get_post_headers_charset_and_relative_urls():
    req = parse_url(
        "https://example.com/search?q={{key}}&page={{page}}|User-Agent=UA|char=gbk",
        keyword="三体",
        page=2,
    )

    assert req == {
        "url": "https://example.com/search?q=%E4%B8%89%E4%BD%93&page=2",
        "method": "GET",
        "headers": {"User-Agent": "UA"},
        "body": None,
        "charset": "gbk",
    }

    post = parse_url(
        'https://example.com/search,{"method":"POST","body":"kw={{key}}","headers":{"X-Test":"1"}}',
        keyword="三体",
    )

    assert post["method"] == "POST"
    assert post["body"] == "kw=%E4%B8%89%E4%BD%93"
    assert post["headers"] == {"X-Test": "1"}

    relative_post = parse_url(
        '/modules/article/search.php,{"method":"POST","body":"searchkey={{key}}","charset":"gbk"}',
        keyword="三体",
        source_url="https://example.com/source",
    )

    assert relative_post == {
        "url": "https://example.com/modules/article/search.php",
        "method": "POST",
        "headers": {},
        "body": "searchkey=%E4%B8%89%E4%BD%93",
        "charset": "gbk",
    }

    single_quote_config = parse_url(
        "/modules/article/search.php?searchkey={{key}},{'charset':'gbk'}",
        keyword="三体",
        source_url="https://example.com/source",
    )

    assert single_quote_config == {
        "url": "https://example.com/modules/article/search.php?searchkey=%E4%B8%89%E4%BD%93",
        "method": "POST",
        "headers": {},
        "body": "",
        "charset": "gbk",
    }

    js_object_config = parse_url(
        '/search.html,{method: "post", body: "searchkey={{key}}&searchtype=all"}',
        keyword="三体",
        source_url="https://example.com/source",
    )

    assert js_object_config == {
        "url": "https://example.com/search.html",
        "method": "POST",
        "headers": {},
        "body": "searchkey=%E4%B8%89%E4%BD%93&searchtype=all",
        "charset": None,
    }

    shorthand = parse_url("https://example.com/search@kw={{key}}", keyword="三体")
    assert shorthand["method"] == "POST"
    assert shorthand["body"] == "kw=%E4%B8%89%E4%BD%93"

    relative = parse_url("/search?q={{searchKey}}", keyword="三体", source_url="https://example.com/source")
    assert relative["url"] == "https://example.com/search?q=%E4%B8%89%E4%BD%93"
    assert make_absolute_url("chapter/1.html", "https://example.com/book/index.html") == "https://example.com/book/chapter/1.html"
    assert make_absolute_url("?q=三体", "https://example.com/search") == "https://example.com/search?q=三体"


def test_url_parser_handles_legado_source_key_expressions():
    req = parse_url(
        "{{cookie.removeCookie(source.getKey())}}\n/ss/?searchkey={{key}}",
        keyword="斗破苍穹",
        source_url="https://www.69hsz.com",
    )

    assert req["url"] == "https://www.69hsz.com/ss/?searchkey=%E6%96%97%E7%A0%B4%E8%8B%8D%E7%A9%B9"

    host_req = parse_url(
        "https://{{source.getKey()}}/search?q={{key}}",
        keyword="三体",
        source_url="https://example.com/source",
    )

    assert host_req["url"] == "https://example.com/search?q=%E4%B8%89%E4%BD%93"


def test_url_parser_removes_control_whitespace_from_templates():
    req = parse_url(
        "https://example.com/search\t?q={{key}}\n&page={{page}}",
        keyword="三体",
        page=2,
    )

    assert req["url"] == "https://example.com/search?q=%E4%B8%89%E4%BD%93&page=2"


def test_url_parser_drops_unresolved_complex_templates():
    req = parse_url(
        "{{String(java.connect(source.getKey()).raw().request().url())}}",
        keyword="三体",
        source_url="https://example.com",
    )

    assert req["url"] == ""


def test_url_parser_executes_js_search_url_templates():
    req = parse_url(
        '@js: "https://example.com/search?key=" + key + "&page=" + page + "&sign=" + java.md5Encode(key);',
        keyword="abc",
        page=3,
    )

    assert req["url"] == "https://example.com/search?key=abc&page=3&sign=900150983cd24fb0d6963f7d28e17f72"

    empty_req = parse_url("@js: '/'", keyword="abc")
    assert empty_req["url"] == ""

    no_host_req = parse_url("@js: 'https://'", keyword="abc")
    assert no_host_req["url"] == ""


def test_parse_headers_coerces_values_to_strings():
    assert parse_headers('{"User-Agent":"UA","ismobile":0,"Skip":null}') == {
        "User-Agent": "UA",
        "ismobile": "0",
    }


def test_js_engine_executes_snippets_with_variables_and_helpers():
    reset_js()

    assert execute_js("@js: result + '-' + baseUrl", "正文", baseUrl="https://example.com") == "正文-https://example.com"
    assert execute_js("<js>java.base64Decode(java.base64Encode('测试'))</js>") == "测试"
    assert execute_js("@js: java.md5Encode('abc')") == "900150983cd24fb0d6963f7d28e17f72"


def test_js_engine_supports_aes_base64_decode_helper():
    from Crypto.Cipher import AES

    reset_js()
    plaintext = "第一段正文\n第二段正文"
    digest = hashlib.md5("secret".encode()).hexdigest()
    iv = digest[:16]
    key = digest[16:]
    payload = plaintext.encode()
    pad_len = AES.block_size - len(payload) % AES.block_size
    payload += bytes([pad_len]) * pad_len
    encrypted = AES.new(key.encode(), AES.MODE_CBC, iv.encode()).encrypt(payload)
    encoded = base64.b64encode(encrypted).decode()

    assert execute_js(
        "@js: java.aesBase64DecodeToString(result, key, 'AES/CBC/PKCS5padding', baseUrl)",
        encoded,
        key=key,
        baseUrl=iv,
    ) == plaintext


def test_rule_parser_executes_legado_js_snippets_for_json_and_variables():
    reset_js()
    parser = RuleParser()
    payload = '{"items":[{"name":"大道争锋","id":"book-1"}]}'

    assert parser.parse("@js: JSON.parse(result).items[0].name + '@' + baseUrl", payload, base_url="https://example.com") == "大道争锋@https://example.com"
    assert execute_js("@js: keyword + '-' + page", "", keyword="大道争锋", page=3) == "大道争锋-3"


def test_rule_parser_handles_multiline_legado_pipeline():
    parser = RuleParser()
    item = {"bid": "123", "title": "测试书"}

    rule = """
    $.bid
    <js>1100000000 + parseInt(result)</js>
    https://bookshelf.example.com/book?id={{result}}
    """

    assert parser.parse_element(rule, item) == "https://bookshelf.example.com/book?id=1100000123"

    template_rule = "书名：{{$.title}}\n##书名：(.*)"
    assert parser.parse_element(template_rule, item) == "测试书"


def test_rule_parser_handles_single_brace_jsonpath_templates():
    parser = RuleParser()
    item = {"NovelID": 123, "NovelCover": "cover.jpg"}

    assert parser.parse_element("/i/{$.NovelID}/", item) == "/i/123/"
    assert parser.parse_element("https://img.example/{$.NovelCover}", item) == "https://img.example/cover.jpg"


def test_rule_parser_handles_jsonpath_inline_js_postprocessing():
    parser = RuleParser()

    assert parser.parse_element("$.id@js:'https://example.com/book/' + result", {"id": 42}) == "https://example.com/book/42"


def test_rule_parser_does_not_split_multiline_js_script():
    parser = RuleParser()
    script = """@js:
var value = JSON.parse(result).name;
value + '-ok';
"""

    assert parser.parse(script, '{"name":"测试"}') == "测试-ok"


def test_rule_parser_does_not_treat_js_operators_as_compound_rules():
    parser = RuleParser()
    script = "@js: var ok = true; ok && result ? 'yes' : 'no';"

    assert parser.parse(script, "value") == "yes"
