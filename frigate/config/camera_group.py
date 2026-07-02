from typing import List, Union

from pydantic import Field, field_validator

from .base import FrigateBaseModel

__all__ = ["CameraGroupConfig"]


class CameraGroupConfig(FrigateBaseModel):
    """Represents a group of cameras."""

    cameras: Union[str, List[str]] = Field(
        default_factory=list, title="List of cameras in this group."
    )
    icon: str = Field(default="generic", title="Icon that represents camera group.")
    order: int = Field(default=0, title="Sort order for group.")
    users: Union[str, List[str]] = Field(
        default_factory=list,
        title="List of users allowed to see this group. Empty means all users.",
    )

    @field_validator("cameras", mode="before")
    @classmethod
    def validate_cameras(cls, v):
        if isinstance(v, str) and "," not in v:
            return [v]

        return v

    @field_validator("users", mode="before")
    @classmethod
    def validate_users(cls, v):
        if isinstance(v, str):
            return [user.strip() for user in v.split(",") if user.strip()]

        return v

