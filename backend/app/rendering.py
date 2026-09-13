"""将 Markdown/HTML 渲染为受白名单保护的 HTML,并安全链接已有标签."""

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
    """只在已清理 HTML 的普通文本节点中添加站内标签链接."""

    def __init__(self, slugs: dict[str, str]) -> None:
        """初始化标签名称键到 slug 的映射及 HTML 输出缓冲区."""
        super().__init__(convert_charrefs=False)
        self.slugs = slugs
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """保留开始标签,并在链接或代码节点内暂停 hashtag 替换."""
        del attrs
        self.parts.append(self.get_starttag_text())
        if tag.lower() in {"a", "code", "pre", "script", "style"}:
            self._ignored_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """保留自闭合标签,不对其属性或内容做标签替换."""
        del tag, attrs
        self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        """保留结束标签,并恢复被忽略节点外的 hashtag 处理状态."""
        self.parts.append(f"</{tag}>")
        if tag.lower() in {"a", "code", "pre", "script", "style"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)

    def handle_data(self, data: str) -> None:
        """在普通文本中把已存在的 hashtag 映射为站内安全链接."""
        if self._ignored_depth:
            self.parts.append(data)
            return

        def replacement(match) -> str:
            """替换单个已知标签,并对显示名称和 URL 片段分别转义."""
            name = match.group(1)
            slug = self.slugs.get(name_key(name))
            if not slug:
                return match.group(0)
            return f'<a class="hashtag-link" href="/tag/{quote(slug, safe="")}">#{escape(name)}</a>'

        self.parts.append(_HASHTAG_PATTERN.sub(replacement, data))

    def handle_entityref(self, name: str) -> None:
        """原样保留实体引用,避免解析再输出时改变正文."""
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        """原样保留数字字符引用."""
        self.parts.append(f"&#{name};")


def linkify_hashtags(html: str, tags: list[dict]) -> str:
    """依据 Note 已关联的标签,把正文中的 hashtag 链接到标签页."""
    linker = _HashtagLinker({name_key(tag["name"]): tag["slug"] for tag in tags})
    linker.feed(html)
    linker.close()
    return "".join(linker.parts)


def clean_html(value: str) -> str:
    """用 nh3 白名单清理 HTML,移除脚本,危险属性和危险 URL scheme."""
    return nh3.clean(
        value,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
    )


def render_content(raw: str, content_format: str | None = None) -> str:
    """按内容格式渲染并清理 HTML;content_format 仅供 About 兼容 Markdown."""
    if content_format is None:
        return clean_html(raw)
    if content_format == "markdown":
        return clean_html(_MARKDOWN.render(raw))
    if content_format == "html":
        return clean_html(raw)
    raise ValueError("content_format")
