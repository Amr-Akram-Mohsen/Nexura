"""Pydantic validation schemas for API request payloads."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class InteractionPayload(BaseModel):
    """Validation schema for user interaction endpoint."""

    model_config = ConfigDict(extra="ignore")

    action: Literal["like", "dislike", "save", "share", "impression"]
    target_id: int = Field(gt=0)
    target_type: Literal["content", "comment"] = "content"
    collection: str = Field(default="General", max_length=100)
    channel: str = Field(default="copy", max_length=50)

    @model_validator(mode="before")
    @classmethod
    def resolve_target_id(cls, data: Any) -> Any:
        """Map content_id alias to target_id if target_id is omitted."""
        if isinstance(data, dict):
            if "target_id" not in data or data.get("target_id") is None:
                if "content_id" in data and data.get("content_id") is not None:
                    data["target_id"] = data["content_id"]
        return data


class CommentPayload(BaseModel):
    """Validation schema for comment submission endpoint."""

    model_config = ConfigDict(extra="ignore")

    content_id: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=2000)
    parent_id: int | None = Field(default=None)


class NewsletterSubscribePayload(BaseModel):
    """Validation schema for newsletter subscription."""

    model_config = ConfigDict(extra="ignore")

    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class BatchContentPayload(BaseModel):
    """Validation schema for admin batch content mutation."""

    model_config = ConfigDict(extra="ignore")

    action: Literal["publish", "unpublish", "activate", "deactivate", "delete"]
    content_ids: list[int] = Field(min_length=1)
