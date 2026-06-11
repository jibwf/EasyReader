"""Regex parser for Legado ## syntax.

Legado regex rules:
- `##regex` — match and return first group (or full match)
- `##regex##replacement` — match and replace
- `###regex` — match and return all groups joined
"""

import re


def parse(rule: str, content: str) -> str:
    if not rule or not content:
        return ""

    # Strip leading ## markers
    if rule.startswith("###"):
        return _match_all_groups(rule[3:], content)

    if not rule.startswith("##"):
        return content

    rule = rule[2:]

    # Check for replacement pattern
    parts = rule.split("##")
    if len(parts) == 2:
        pattern, replacement = parts
        return _replace(pattern, replacement, content)

    return _match_first(rule, content)


def _match_first(pattern: str, content: str) -> str:
    try:
        m = re.search(pattern, content, re.DOTALL)
        if not m:
            return ""
        if m.groups():
            return m.group(1)
        return m.group(0)
    except re.error:
        return ""


def _match_all_groups(pattern: str, content: str) -> str:
    try:
        m = re.search(pattern, content, re.DOTALL)
        if not m:
            return ""
        return "".join(g for g in m.groups() if g)
    except re.error:
        return ""


def _replace(pattern: str, replacement: str, content: str) -> str:
    try:
        return re.sub(pattern, replacement, content)
    except re.error:
        return content
