"""Общее для схем API."""

from pydantic import BaseModel, ConfigDict


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)
