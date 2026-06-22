from typing import Annotated

from pydantic import BaseModel, Field

Markdown = Annotated[
    str,
    Field(description="Markdown-formatted text")
]

class Article(BaseModel):
    title: str = Field(description="Article title")
    body: Markdown = Field(description="Markdown article body")
    url: str = Field(description="Article URL")

class Attachment(BaseModel):
    filename: str = Field(description="Name of the attached file")
    content_type: str = Field(description="MIME type of the attached file, only non-binary files are supported, eg text/csv, application/json, text/plain, etc.")
    size_kb: int = Field(description="Size of the attached file in kilobytes")
    payload: str = Field(description="Contents of the attached file")