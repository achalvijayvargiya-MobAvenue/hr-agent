from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_agent.database import Base


class ZohoOAuthToken(Base):
    """Persistent storage for Zoho OAuth tokens."""

    __tablename__ = "zoho_oauth_tokens"

    service_name: Mapped[str] = mapped_column(String, primary_key=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ZohoOAuthToken service_name={self.service_name!r} expires_at={self.expires_at!r}>"
