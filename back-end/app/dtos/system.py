from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.prompts import PromptKey


class SystemPromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    param: PromptKey
    value: str


class UpdatePromptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=100_000)
    expected_value: str = Field(max_length=100_000)


class UpdateRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=1, max_length=255)
    role: Literal["ADMIN", "SUPER"]


class UpdateRoleResponse(BaseModel):
    message: str
    role: Literal["ADMIN", "SUPER"]
