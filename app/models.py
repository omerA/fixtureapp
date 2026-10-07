from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    subscriptions = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    team_key = Column(String, nullable=False)   # "Tenafly-B12A-Schwartzberg"
    division = Column(String, nullable=False)    # "B12A"
    club = Column(String, nullable=False)        # "Tenafly"
    coach = Column(String, nullable=False)       # "Schwartzberg"
    # NULL = active (current season); "2026-spring" = archived for that season
    season = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="subscriptions")

    # Unique among active rows only, so an archived row never blocks
    # following a team whose key recurs in a later season.
    __table_args__ = (
        Index(
            "uq_user_team_active", "user_id", "team_key", unique=True,
            sqlite_where=text("season IS NULL"),
            postgresql_where=text("season IS NULL"),
        ),
    )
