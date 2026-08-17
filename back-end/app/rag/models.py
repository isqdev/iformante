from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ModelMessage:
    role: Literal["assistant", "user"]
    content: str
