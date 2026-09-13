from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(StrictModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class CategoryLink(StrictModel):
    category_id: int = Field(gt=0)
    is_primary: bool = False


class ItemLink(StrictModel):
    item_id: int = Field(gt=0)
    context_label: str | None = Field(default=None, max_length=200)
    progress_text: str | None = Field(default=None, max_length=200)


class NoteWrite(StrictModel):
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
    category_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    subtitle: str = Field(default="", max_length=300)
    creator: str = Field(default="", max_length=200)
    visibility: Literal["public", "private"] = "private"
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ItemPatch(StrictModel):
    category_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=300)
    creator: str | None = Field(default=None, max_length=200)
    metadata_json: dict[str, Any] | None = None


class VisibilityRequest(StrictModel):
    visibility: Literal["public", "private"]


class CategoryWrite(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: int = Field(gt=0)


class CategoryPatch(StrictModel):
    name: str = Field(min_length=1, max_length=100)


class TagWrite(StrictModel):
    name: str = Field(min_length=1, max_length=64)


class TagPatch(StrictModel):
    name: str = Field(min_length=1, max_length=64)


class SettingsPatch(StrictModel):
    site_title: str | None = Field(default=None, max_length=120)
    site_tagline: str | None = Field(default=None, max_length=240)
    timezone: str | None = Field(default=None, max_length=80)
    now_status: str | None = Field(default=None, max_length=280)
    about_raw: str | None = Field(default=None, max_length=100_000)
    about_format: Literal["markdown", "html"] | None = None
    current_note_id: int | None = Field(default=None, gt=0)
