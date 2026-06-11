"""Rule parser — the central dispatcher for all rule types.

Determines the rule type from its prefix/pattern and delegates to the
appropriate parser. Also handles rule chains (&&, ||, %%).
"""

from lxml import etree
from bs4 import Tag

from backend.engine import css_parser, xpath_parser, jsonpath_parser, regex_parser, js_engine
from backend.engine.rule_chain import split_rules, is_compound


class RuleParser:
    """Stateless rule parser that dispatches to sub-parsers."""

    def parse(self, rule: str, content: str | dict | Tag, base_url: str = "") -> str | list[str]:
        if not rule or not content:
            return ""

        rule = rule.strip()

        if self._is_multiline(rule) and not self._is_js_rule(rule):
            return self._parse_multiline(rule, content, base_url)

        if self._is_js_rule(rule):
            return self._parse_single(rule, content, base_url)

        # Handle compound rules (&&, ||, %%)
        if is_compound(rule):
            return self._parse_compound(rule, content, base_url)

        return self._parse_single(rule, content, base_url)

    def parse_list(self, rule: str, content: str | dict, base_url: str = ""):
        """Parse a rule that should return a list of elements/dicts."""
        if not rule or not content:
            return []

        rule = rule.strip()

        if rule.startswith("@css:") or self._is_jsoup(rule):
            return css_parser.parse_list(rule, content)
        elif rule.startswith("//") or rule.startswith(".//") or rule.startswith("./") or rule.startswith("@xpath:"):
            xpath_rule = rule.removeprefix("@xpath:")
            return xpath_parser.parse_list(xpath_rule, content)
        elif rule.startswith("$.") or rule.startswith("@json:"):
            return jsonpath_parser.parse_list(rule, content)
        else:
            return css_parser.parse_list(rule, content)

    def parse_element(self, rule: str, element, base_url: str = "") -> str:
        """Parse a rule against a single element (Tag or dict or etree Element)."""
        if not rule:
            return ""

        rule = rule.strip()

        if self._is_multiline(rule) and not self._is_js_rule(rule):
            return self._parse_multiline(rule, element, base_url)

        if self._is_js_rule(rule):
            return self._parse_single(rule, element, base_url)

        if "{$" in rule:
            return self._render_template(rule, element, base_url, "")

        if is_compound(rule):
            return self._parse_compound(rule, element, base_url)

        if isinstance(element, dict):
            # Handle inline regex: $.field##regex##replacement
            if "##" in rule and not rule.startswith("##"):
                parts = rule.split("##", 1)
                base_result = self.parse_element(parts[0], element, base_url)
                if base_result:
                    return regex_parser.parse("##" + parts[1], base_result if isinstance(base_result, str) else str(base_result))
                return ""
            if "@js:" in rule and not rule.startswith("@js:"):
                base_rule, js_rule = rule.split("@js:", 1)
                base_result = self.parse_element(base_rule, element, base_url)
                text = base_result if isinstance(base_result, str) else str(base_result or "")
                return js_engine.execute("@js:" + js_rule, text, baseUrl=base_url)
            # JSON element — use jsonpath or direct key access
            if rule.startswith("$.") or rule.startswith("@json:"):
                return jsonpath_parser.get_value(element, rule)
            # Simple key access
            return str(element.get(rule, ""))

        if isinstance(element, etree._Element):
            if rule.startswith("//") or rule.startswith(".//") or rule.startswith("./") or rule.startswith("@xpath:"):
                return xpath_parser.get_element_text(element, rule)
            text = etree.tostring(element, method="html", encoding="unicode")
            return self._parse_single(rule, text, base_url)

        if isinstance(element, (Tag, str)):
            return self._parse_single(rule, element, base_url)

        return ""

    def _parse_single(self, rule: str, content: str | dict | Tag, base_url: str) -> str:
        # Handle inline regex post-processing: rule##regex##replacement
        # (e.g. $.groupID##.*_## means: get jsonpath then regex-replace)
        if "##" in rule and not rule.startswith("##"):
            parts = rule.split("##", 1)
            base_rule = parts[0]
            regex_rule = "##" + parts[1]
            result = self._parse_single(base_rule, content, base_url)
            if result:
                text = result if isinstance(result, str) else str(result)
                return regex_parser.parse(regex_rule, text)
            return ""

        # JS rules
        if rule.startswith("<js>") or rule.startswith("@js:"):
            text = content if isinstance(content, str) else ""
            return js_engine.execute(rule, text, baseUrl=base_url)

        # JSONPath
        if rule.startswith("$.") or rule.startswith("@json:"):
            return jsonpath_parser.parse(rule, content)

        # XPath
        if rule.startswith("//") or rule.startswith(".//") or rule.startswith("./") or rule.startswith("@xpath:"):
            text = content if isinstance(content, str) else str(content)
            return xpath_parser.parse(rule, text)

        # Regex (## prefix)
        if rule.startswith("##") or rule.startswith("###"):
            text = content if isinstance(content, str) else str(content)
            return regex_parser.parse(rule, text)

        # CSS (@css: prefix or JSOUP shorthand)
        if rule.startswith("@css:") or self._is_jsoup(rule):
            return css_parser.parse(rule, content)

        # Default: try as CSS
        return css_parser.parse(rule, content)

    def _parse_compound(self, rule: str, content, base_url: str) -> str | list[str]:
        operator, parts = split_rules(rule)

        if operator == "&&":
            # Concatenate all results
            results = []
            for part in parts:
                r = self._parse_single(part, content, base_url)
                if isinstance(r, list):
                    results.extend(r)
                elif r:
                    results.append(r)
            return "\n".join(results) if results else ""

        elif operator == "||":
            # First non-empty result
            for part in parts:
                r = self._parse_single(part, content, base_url)
                if r:
                    return r
            return ""

        elif operator == "%%":
            # Format template (first part is template, rest are values)
            if len(parts) < 2:
                return self._parse_single(parts[0], content, base_url) if parts else ""
            template = parts[0]
            for i, part in enumerate(parts[1:]):
                val = self._parse_single(part, content, base_url)
                if isinstance(val, list):
                    val = val[0] if val else ""
                template = template.replace(f"${{{i}}}", val)
            return template

        return ""

    def _is_multiline(self, rule: str) -> bool:
        return "\n" in rule and len([line for line in rule.splitlines() if line.strip()]) > 1

    def _is_js_rule(self, rule: str) -> bool:
        stripped = rule.strip()
        return stripped.startswith("<js>") or stripped.startswith("@js:")

    def _parse_multiline(self, rule: str, content, base_url: str) -> str:
        """Parse a common Legado line pipeline.

        Typical shape:
            $.bid
            <js>1100000000+parseInt(result)</js>
            https://example.com/book?id={{result}}
        """
        parts = [line.strip() for line in rule.splitlines() if line.strip()]
        result = ""
        for index, part in enumerate(parts):
            if "{{" in part and "}}" in part:
                result = self._render_template(part, content, base_url, result)
                continue

            if index == 0:
                parsed = self.parse_element(part, content, base_url)
            elif part.startswith("<js>") or part.startswith("@js:") or part.startswith("##") or part.startswith("###"):
                parsed = self._parse_single(part, result, base_url)
            else:
                parsed = self.parse_element(part, content, base_url)

            if isinstance(parsed, list):
                result = parsed[0] if parsed else ""
            else:
                result = parsed or ""
        return result

    def _render_template(self, template: str, content, base_url: str, result: str) -> str:
        import re

        def replace(match: re.Match) -> str:
            expr = match.group(1).strip()
            if expr == "result":
                return result
            parsed = self.parse_element(expr, content, base_url)
            if isinstance(parsed, list):
                return parsed[0] if parsed else ""
            return parsed or ""

        rendered = re.sub(r"\{\{(.+?)\}\}", replace, template)

        def replace_dollar(match: re.Match) -> str:
            parsed = self.parse_element("$" + match.group(1).strip(), content, base_url)
            if isinstance(parsed, list):
                return parsed[0] if parsed else ""
            return parsed or ""

        return re.sub(r"\{\$(.+?)\}", replace_dollar, rendered)

    def _is_jsoup(self, rule: str) -> bool:
        """Check if rule looks like JSOUP shorthand (class.x, tag.x, id.x, text.x)."""
        prefixes = ("class.", "tag.", "id.", "text.", "children")
        return any(rule.startswith(p) for p in prefixes)
