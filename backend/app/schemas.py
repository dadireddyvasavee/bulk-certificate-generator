from datetime import date
from typing import Annotated
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator
from .config import MAX_BATCH

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class RawRecipient(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(max_length=200)
    email: str = Field(max_length=320)


class ValidRecipient(BaseModel):
    name: Text
    email: EmailStr

    @field_validator("name")
    @classmethod
    def printable(cls, value: str) -> str:
        if any(ord(c) < 32 for c in value):
            raise ValueError("Control characters are not allowed")
        return value


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    organization: Text
    title: Text
    statement: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]
    signatory: str = Field(default="", max_length=200)
    issue_date: date
    recipients: list[RawRecipient] = Field(min_length=1, max_length=MAX_BATCH)

    @field_validator("event", "organization", "title", "statement", "signatory")
    @classmethod
    def printable(cls, value: str) -> str:
        if any(ord(c) < 32 for c in value):
            raise ValueError("Control characters are not allowed")
        return value


class JobView(BaseModel):
    id: str
    event: str
    organization: str
    title: str
    statement: str
    signatory: str
    issue_date: str
    status: str
    created_at: float
    started_at: float | None
    completed_at: float | None
    total: int
    pending: int
    processing: int
    succeeded: int
    failed: int
    progress: float


class RecipientView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    job_id: str
    name: str
    email: str
    status: str
    certificate_id: str | None
    error_code: str | None
    error: str | None
    attempts: int


class JobPage(BaseModel):
    items: list[JobView]
    total: int
    page: int
    page_size: int


class RecipientPage(BaseModel):
    items: list[RecipientView]
    total: int
    page: int
    page_size: int


class Metrics(BaseModel):
    jobs: int
    recipients: int
    processed: int
    succeeded: int
    failed: int
    processing: int
    pending: int
