import datetime
from sqlalchemy import BigInteger, Text, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from database.database import Base


class ModernizationHistory(Base):
    __tablename__ = "modernization_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    generated_code: Mapped[str] = mapped_column(Text, nullable=True)
    report: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, 
        default=datetime.datetime.utcnow
    )