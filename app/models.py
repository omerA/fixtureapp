from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True, index=True)
    teamsnap_id = Column(String, unique=True, nullable=True, index=True)
    teamsnap_access_token = Column(String, nullable=True)
    teamsnap_refresh_token = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    subscriptions = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan"
    )
    teamsnap_links = relationship(
        "TeamSnapLink", back_populates="user", cascade="all, delete-orphan"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    team_key = Column(String, nullable=False)   # "Tenafly-B12A-Schwartzberg"
    division = Column(String, nullable=False)    # "B12A"
    club = Column(String, nullable=False)        # "Tenafly"
    coach = Column(String, nullable=False)       # "Schwartzberg"
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="subscriptions")

    __table_args__ = (UniqueConstraint("user_id", "team_key", name="uq_user_team"),)


class TeamSnapLink(Base):
    __tablename__ = "teamsnap_links"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    teamsnap_team_id = Column(String, nullable=False)
    teamsnap_team_name = Column(String, nullable=False)
    ncsa_subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    roster_json = Column(Text, nullable=True)       # JSON list of {"name": str}
    roster_synced_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="teamsnap_links")
    subscription = relationship("Subscription")
