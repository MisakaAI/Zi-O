from __future__ import annotations

import nh3
from markdown_it import MarkdownIt

_MARKDOWN = MarkdownIt("commonmark", {"html": True, "linkify": False, "typographer": False})
_ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "code", "del", "div", "em", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "i", "kbd", "li", "ol", "p", "pre", "q", "s", "small", "span", "strong", "sub", "sup", "table",
    "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul",
}
_ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "code": {"class"},
    "div": {"class"},
    "span": {"class"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}


def clean_html(value: str) -> str:
    return nh3.clean(
        value,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
    )


def render_content(raw: str, content_format: str | None = None) -> str:
    """清理正文 HTML；content_format 仅供仍支持 Markdown 的 About 使用。"""
    if content_format is None:
        return clean_html(raw)
    if content_format == "markdown":
        return clean_html(_MARKDOWN.render(raw))
    if content_format == "html":
        return clean_html(raw)
    raise ValueError("content_format")
