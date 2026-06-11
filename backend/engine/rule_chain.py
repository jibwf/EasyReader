"""Rule chain parser for Legado composite rules.

Operators:
- `&&` — concatenate all results
- `||` — return first non-empty result
- `%%` — format output with template (index-based)
"""


def split_rules(rule: str) -> tuple[str, list[str]]:
    """Split a composite rule into operator and parts.

    Returns (operator, [rule_parts]).
    Operator is one of: '&&', '||', '%%', or '' for single rules.
    """
    if "&&" in rule:
        return "&&", [r.strip() for r in rule.split("&&")]
    if "||" in rule:
        return "||", [r.strip() for r in rule.split("||")]
    if "%%" in rule:
        return "%%", [r.strip() for r in rule.split("%%")]
    return "", [rule]


def is_compound(rule: str) -> bool:
    return "&&" in rule or "||" in rule or "%%" in rule
