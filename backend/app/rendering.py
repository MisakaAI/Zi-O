from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import quote

import nh3
from markdown_it import MarkdownIt

from .domain import name_key

_MARKDOWN = MarkdownIt("commonmark", {"html": True, "linkify": False, "typographer": False})
_ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "code", "del", "div", "em", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "i", "img", "kbd", "li", "ol", "p", "pre", "q", "s", "small", "span", "strong", "sub", "sup", "table",
    "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul",
}
_ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "code": {"class"},
    "div": {"class"},
    "img": {"alt", "src", "title"},
    "span": {"class"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}

_HASHTAG_PATTERN = re.compile(r"(?<![\w#])#([\w]{1,64})(?!\w)", re.UNICODE)


class _HashtagLinker(HTMLParser):
    """只在已清理 HTML 的普通文本节点中添加站内标签链接。"""

    def __init__(self, slugs: dict[str, str]) -> None:
        super().__init__(convert_charrefs=False)
        self.slugs = slugs
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        self.parts.append(self.get_starttag_text())
        if tag.lower() in {"a", "code", "pre", "script", "style"}:
            self._ignored_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del tag, attrs
        self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")
        if tag.lower() in {"a", "code", "pre", "script", "style"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            self.parts.append(data)
            return

        def replacement(match) -> str:
            name = match.group(1)
            slug = self.slugs.get(name_key(name))
            if not slug:
                return match.group(0)
            return f'<a class="hashtag-link" href="/tag/{quote(slug, safe="")}">#{escape(name)}</a>'

        self.parts.append(_HASHTAG_PATTERN.sub(replacement, data))

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")


def linkify_hashtags(html: str, tags: list[dict]) -> str:
    linker = _HashtagLinker({name_key(tag["name"]): tag["slug"] for tag in tags})
    linker.feed(html)
    linker.close()
    return "".join(linker.parts)


def clean_html(value: str) -> str:
    return nh3.clean(
        value,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
    )


def render_content(raw: str, content_format: str | None = None) -> str:
    """清理正文 HTML。content_format 仅供仍支持 Markdown 的 About 使用。"""
    if content_format is None:
        return clean_html(raw)
    if content_format == "markdown":
        return clean_html(_MARKDOWN.render(raw))
    if content_format == "html":
        return clean_html(raw)
    raise ValueError("content_format")
