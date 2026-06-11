"""JSONPath parser using jsonpath-ng."""

import json

from jsonpath_ng.ext import parse as jp_parse


def parse(rule: str, content: str | dict) -> str | list[str]:
    if not rule:
        return ""

    rule = rule.removeprefix("@json:")

    data = _ensure_dict(content)
    if data is None:
        return ""

    try:
        expr = jp_parse(rule)
        matches = expr.find(data)
    except Exception:
        return ""

    if not matches:
        return ""

    results = [_to_str(m.value) for m in matches]
    results = [r for r in results if r]
    if not results:
        return ""
    return results if len(results) > 1 else results[0]


def parse_list(rule: str, content: str | dict) -> list[dict]:
    if not rule:
        return []

    rule = rule.removeprefix("@json:")

    data = _ensure_dict(content)
    if data is None:
        return []

    try:
        expr = jp_parse(rule)
        matches = expr.find(data)
    except Exception:
        return []

    return [m.value for m in matches if isinstance(m.value, dict)]


def get_value(data: dict, rule: str) -> str:
    if not rule:
        return ""

    rule = rule.removeprefix("@json:")

    try:
        expr = jp_parse(rule)
        matches = expr.find(data)
    except Exception:
        return ""

    if not matches:
        return ""
    return _to_str(matches[0].value)


def _ensure_dict(content: str | dict) -> dict | list | None:
    if isinstance(content, (dict, list)):
        return content
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None


def _to_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)
