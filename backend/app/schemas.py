"""FastAPI 请求体模型,集中声明字段类型,枚举值和输入上限."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """禁止未声明字段进入 API,避免客户端悄悄提交未处理的数据."""

    model_config = ConfigDict(extra="forbid")


class LoginRequest(StrictModel):
    """管理员登录所需的用户名和密码."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class CategoryLink(StrictModel):
    """Note 与分类的关联请求,标记其中是否为主分类."""

    category_id: int = Field(gt=0)
    is_primary: bool = False


class ItemLink(StrictModel):
    """Note 与 Item 的关联请求,附带可选上下文和进度描述."""

    item_id: int = Field(gt=0)
    context_label: str | None = Field(default=None, max_length=200)
    progress_text: str | None = Field(default=None, max_length=200)


class NoteWrite(StrictModel):
    """创建 Note 的完整请求模型;正文真源为 HTML 字符串."""

    title: str = Field(default="", max_length=200)
    content_raw: str = Field(default="", max_length=1_048_576)
    started_at: str | int | float | None = None
    ended_at: str | int | float | None = None
    visibility: Literal["public", "private"] = "private"
    static_path: str | None = Field(default=None, max_length=512)
    categories: list[CategoryLink] | None = None
    items: list[ItemLink] | None = None
    tag_ids: list[int] | None = None


class NotePatch(StrictModel):
    """部分更新 Note 的请求模型,未提交的字段保持原值."""

    title: str | None = Field(default=None, max_length=200)
    content_raw: str | None = Field(default=None, max_length=1_048_576)
    started_at: str | int | float | None = None
    ended_at: str | int | float | None = None
    visibility: Literal["public", "private"] | None = None
    static_path: str | None = Field(default=None, max_length=512)
    categories: list[CategoryLink] | None = None
    items: list[ItemLink] | None = None
    tag_ids: list[int] | None = None


class ItemWrite(StrictModel):
    """创建 Item 的请求模型,元数据由服务层按根分类进一步校验."""

    category_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    subtitle: str = Field(default="", max_length=300)
    creator: str = Field(default="", max_length=200)
    visibility: Literal["public", "private"] = "private"
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ItemPatch(StrictModel):
    """部分更新 Item 的请求模型."""

    category_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=300)
    creator: str | None = Field(default=None, max_length=200)
    metadata_json: dict[str, Any] | None = None


class VisibilityRequest(StrictModel):
    """Item 可见性变更请求,仅允许 public 或 private."""

    visibility: Literal["public", "private"]


class CategoryWrite(StrictModel):
    """创建子分类的请求模型."""

    name: str = Field(min_length=1, max_length=100)
    parent_id: int = Field(gt=0)


class CategoryPatch(StrictModel):
    """修改子分类名称的请求模型."""

    name: str = Field(min_length=1, max_length=100)


class TagWrite(StrictModel):
    """创建普通标签的请求模型."""

    name: str = Field(min_length=1, max_length=64)


class TagPatch(StrictModel):
    """修改普通标签名称的请求模型."""

    name: str = Field(min_length=1, max_length=64)


class SettingsPatch(StrictModel):
    """站点设置的部分更新请求模型."""

    site_title: str | None = Field(default=None, max_length=120)
    site_tagline: str | None = Field(default=None, max_length=240)
    timezone: str | None = Field(default=None, max_length=80)
    now_status: str | None = Field(default=None, max_length=280)
    about_raw: str | None = Field(default=None, max_length=100_000)
    about_format: Literal["markdown", "html"] | None = None
    current_note_id: int | None = Field(default=None, gt=0)
