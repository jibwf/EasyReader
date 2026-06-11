"""XPath parser using lxml."""

from lxml import etree


def parse(rule: str, content: str) -> str | list[str]:
    if not rule:
        return ""

    rule = rule.removeprefix("@xpath:")

    tree = _parse_html(content)
    if tree is None:
        return ""

    results = tree.xpath(rule)
    if not results:
        return ""

    texts = _extract_texts(results)
    if not texts:
        return ""
    return texts if len(texts) > 1 else texts[0]


def parse_list(rule: str, content: str) -> list[etree._Element]:
    if not rule:
        return []

    rule = rule.removeprefix("@xpath:")

    tree = _parse_html(content)
    if tree is None:
        return []

    results = tree.xpath(rule)
    return [r for r in results if isinstance(r, etree._Element)]


def get_element_text(element: etree._Element, rule: str) -> str:
    if not rule:
        return ""

    rule = rule.removeprefix("@xpath:")

    results = element.xpath(rule)
    if not results:
        return ""

    texts = _extract_texts(results)
    return texts[0] if texts else ""


def _parse_html(content: str) -> etree._Element | None:
    if isinstance(content, str):
        try:
            return etree.HTML(content)
        except Exception:
            return None
    return content


def _extract_texts(results: list) -> list[str]:
    texts = []
    for r in results:
        if isinstance(r, etree._Element):
            t = etree.tostring(r, method="text", encoding="unicode")
            if t and t.strip():
                texts.append(t.strip())
        elif isinstance(r, str):
            if r.strip():
                texts.append(r.strip())
        else:
            s = str(r).strip()
            if s:
                texts.append(s)
    return texts
