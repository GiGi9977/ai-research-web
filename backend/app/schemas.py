from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


class PaperIn(CamelModel):
    external_id: str | None = None
    source: str = "openalex"
    title: str = Field(min_length=1)
    authors: list[str] = []
    year: int | None = None
    abstract: str | None = None
    url: str | None = None
    pdf_url: str | None = None


class PaperPatch(CamelModel):
    title: str | None = Field(default=None, min_length=1)
    authors: list[str] | None = None
    year: int | None = None
    abstract: str | None = None


class PaperOut(CamelModel):
    id: int
    external_id: str | None
    source: str
    title: str
    authors: list[str]
    year: int | None
    abstract: str | None
    url: str | None
    pdf_url: str | None
    created_at: datetime

    # populated from ORM attributes via the router, never exposed in full
    has_full_text: bool = False
    has_summary: bool = False


class MessageOut(CamelModel):
    id: int
    role: str
    content: str
    created_at: datetime


class PaperDetail(PaperOut):
    summary: str | None = None
    messages: list[MessageOut] = []
