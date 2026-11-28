from sqlalchemy import String, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base

class VoiceUsage(Base):
    __tablename__ = "voice_usage_daily"
    __table_args__ = (CheckConstraint("characters >= 0", name="ck_voice_usage_nonnegative"),)
    scope: Mapped[str] = mapped_column(String(80), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    characters: Mapped[int] = mapped_column(Integer, default=0)
