HTML_CSS_CASE = {
    "name": "html-css-novel",
    "source": {
        "bookSourceUrl": "https://html.example",
        "bookSourceName": "HTML CSS 源",
        "searchUrl": "https://html.example/search?kw={{key}}",
        "ruleSearch": {
            "bookList": "@css:article.book",
            "name": "@css:a.title@text",
            "author": "@css:.author@text",
            "coverUrl": "@css:img.cover@src",
            "bookUrl": "@css:a.title@href",
            "intro": "@css:.intro@text",
            "kind": "@css:.kind@text",
            "lastChapter": "@css:.latest@text",
        },
        "ruleBookInfo": {},
        "ruleToc": {
            "chapterList": "@css:ol.toc li",
            "chapterName": "@css:a@text",
            "chapterUrl": "@css:a@href",
        },
        "ruleContent": {
            "content": "@css:div.content@html",
            "nextContentUrl": "@css:a.next@href",
        },
    },
    "search_response": """
    <article class="book">
      <a class="title" href="/book/1">长夜余火</a>
      <span class="author">爱潜水的乌贼</span>
      <img class="cover" src="/cover/1.jpg">
      <p class="intro">末日废土</p>
      <span class="kind">科幻</span>
      <span class="latest">终章</span>
    </article>
    """,
    "book_url": "https://html.example/book/1",
    "toc_response": """
    <ol class="toc">
      <li><a href="/book/1/c1.html">第一章 起点</a></li>
      <li><a href="/book/1/c2.html">第二章 出发</a></li>
    </ol>
    """,
    "chapter_url": "https://html.example/book/1/c1.html",
    "content_responses": {
        "https://html.example/book/1/c1.html": """
        <div class="content">
          <p>第一段</p>
          <p>第二段</p>
        </div>
        <a class="next" href="/book/1/c1-2.html">下一页</a>
        """,
        "https://html.example/book/1/c1-2.html": """
        <div class="content">
          <p>第三段</p>
        </div>
        """,
    },
    "expected": {
        "search_name": "长夜余火",
        "search_author": "爱潜水的乌贼",
        "chapter_titles": ["第一章 起点", "第二章 出发"],
        "content": "第一段\n\n第二段\n\n第三段",
    },
}


JSON_API_CASE = {
    "name": "json-api-source",
    "source": {
        "bookSourceUrl": "https://json.example",
        "bookSourceName": "JSON API 源",
        "searchUrl": "https://json.example/api/search?q={{key}}",
        "ruleSearch": {
            "bookList": "$.items[*]",
            "name": "$.title",
            "author": "$.writer",
            "coverUrl": "$.cover",
            "bookUrl": "/book/{{$.id}}",
            "intro": "$.summary",
            "kind": "$.category",
            "lastChapter": "$.last",
        },
        "ruleBookInfo": {},
        "ruleToc": {
            "chapterList": "$.chapters[*]",
            "chapterName": "$.title",
            "chapterUrl": "$.url",
        },
        "ruleContent": {
            "content": "$.paragraphs[*]",
        },
    },
    "search_response": """
    {
      "items": [
        {
          "id": "42",
          "title": "三体",
          "writer": "刘慈欣",
          "cover": "/cover/42.jpg",
          "summary": "文明与宇宙",
          "category": "科幻",
          "last": "死神永生"
        }
      ]
    }
    """,
    "book_url": "https://json.example/book/42",
    "toc_response": """
    {
      "chapters": [
        {"title": "科学边界", "url": "/chapter/42-1"},
        {"title": "台球", "url": "/chapter/42-2"}
      ]
    }
    """,
    "chapter_url": "https://json.example/chapter/42-1",
    "content_responses": {
        "https://json.example/chapter/42-1": '{"paragraphs":["第一段","第二段"]}',
    },
    "expected": {
        "search_name": "三体",
        "search_author": "刘慈欣",
        "chapter_titles": ["科学边界", "台球"],
        "content": "第一段\n第二段",
    },
}


JSON_MANGA_CASE = {
    "name": "json-manga-image-list",
    "source": {
        "bookSourceUrl": "https://manga-json.example",
        "bookSourceName": "JSON 漫画源",
        "bookSourceType": 2,
        "searchUrl": "https://manga-json.example/search?q={{key}}",
        "ruleSearch": {
            "bookList": "$.items[*]",
            "name": "$.title",
            "author": "$.author",
            "coverUrl": "$.cover",
            "bookUrl": "/comic/{{$.id}}",
            "lastChapter": "$.latest",
        },
        "ruleBookInfo": {},
        "ruleToc": {
            "chapterList": "$.episodes[*]",
            "chapterName": "$.name",
            "chapterUrl": "$.url",
        },
        "ruleContent": {
            "content": "$.images[*]",
        },
    },
    "search_response": """
    {
      "items": [
        {
          "id": "m1",
          "title": "测试漫画",
          "author": "漫画作者",
          "cover": "/covers/m1.jpg",
          "latest": "第 2 话"
        }
      ]
    }
    """,
    "book_url": "https://manga-json.example/comic/m1",
    "toc_response": """
    {
      "episodes": [
        {"name": "第 1 话", "url": "/episode/m1-1"},
        {"name": "第 2 话", "url": "/episode/m1-2"}
      ]
    }
    """,
    "chapter_url": "https://manga-json.example/episode/m1-1",
    "content_responses": {
        "https://manga-json.example/episode/m1-1": """
        {
          "images": [
            "https://img.manga-json.example/m1/001.jpg",
            "https://img.manga-json.example/m1/002.jpg"
          ]
        }
        """,
    },
    "expected": {
        "search_name": "测试漫画",
        "search_author": "漫画作者",
        "chapter_titles": ["第 1 话", "第 2 话"],
        "content": "https://img.manga-json.example/m1/001.jpg\nhttps://img.manga-json.example/m1/002.jpg",
    },
}


XPATH_RELATIVE_CASE = {
    "name": "xpath-relative-source",
    "source": {
        "bookSourceUrl": "https://xpath.example",
        "bookSourceName": "XPath 源",
        "searchUrl": "https://xpath.example/search/{{key}}",
        "ruleSearch": {
            "bookList": "//div[@class='result']",
            "name": ".//a[@class='name']/text()",
            "author": ".//span[@class='author']/text()",
            "bookUrl": ".//a[@class='name']/@href",
        },
        "ruleBookInfo": {},
        "ruleToc": {
            "chapterList": "//div[@id='toc']/a",
            "chapterName": "./text()",
            "chapterUrl": "./@href",
        },
        "ruleContent": {
            "content": "//div[@id='content']/p/text()",
        },
    },
    "search_response": """
    <div class="result">
      <a class="name" href="/novel/7">诡秘之主</a>
      <span class="author">爱潜水的乌贼</span>
    </div>
    """,
    "book_url": "https://xpath.example/novel/7",
    "toc_response": """
    <div id="toc">
      <a href="/novel/7/1.html">第一章 绯红</a>
      <a href="/novel/7/2.html">第二章 情况</a>
    </div>
    """,
    "chapter_url": "https://xpath.example/novel/7/1.html",
    "content_responses": {
        "https://xpath.example/novel/7/1.html": """
        <div id="content">
          <p>痛！</p>
          <p>好痛！</p>
        </div>
        """,
    },
    "expected": {
        "search_name": "诡秘之主",
        "search_author": "爱潜水的乌贼",
        "chapter_titles": ["第一章 绯红", "第二章 情况"],
        "content": "痛！\n好痛！",
    },
}


TAURI_SOURCE = """
// @name Tauri 漫画源
// @url https://tauri.example
// @type comic
function search(keyword, page) {
  return [
    {
      name: keyword + " 漫画",
      author: "漫画作者",
      coverUrl: "https://tauri.example/cover.jpg",
      bookUrl: "https://tauri.example/book/1",
      latestChapter: "第 2 话"
    }
  ];
}
function bookInfo(bookUrl) {
  return { name: "测试漫画", author: "漫画作者" };
}
function chapterList(bookUrl) {
  return [
    { title: "第 1 话", url: "https://tauri.example/chapter/1" },
    { title: "第 2 话", url: "https://tauri.example/chapter/2" }
  ];
}
function chapterContent(chapterUrl) {
  return [
    "https://tauri.example/images/1.jpg",
    "https://tauri.example/images/2.jpg"
  ];
}
"""
