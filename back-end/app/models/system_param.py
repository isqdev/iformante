from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_id


class SystemParam(Base):
    __tablename__ = "system_params"

    id: Mapped[str] = mapped_column(String(9), primary_key=True, default=generate_id)
    param: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
