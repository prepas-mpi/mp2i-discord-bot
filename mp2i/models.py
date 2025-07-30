from datetime import timedelta
from typing import Optional

import humanize
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Integer, BigInteger, Column, DateTime, String, Text, ForeignKey
from sqlalchemy.schema import PrimaryKeyConstraint, ForeignKeyConstraint

Base = declarative_base()


class GuildModel(Base):
    __tablename__ = "guilds"

    id: int = Column(BigInteger, primary_key=True)
    name: str = Column(String(50))
    members = relationship("MemberModel", cascade="all, delete")
    roles_message_id: int = Column(BigInteger, unique=True, nullable=True)
    suggestion_message_id: int = Column(BigInteger, unique=True, nullable=True)

    def __repr__(self):
        return f"Guild(id={self.id}, name={self.name})"


class MemberModel(Base):
    __tablename__ = "members"
    __table_args__ = (PrimaryKeyConstraint("id", "guild_id", name="members_pkey"),)
    id: int = Column(BigInteger)
    guild_id: int = Column(BigInteger, ForeignKey("guilds.id", ondelete="CASCADE"))
    name: str = Column(String(50))
    role: str = Column(String(50), nullable=True)
    messages_count: int = Column(Integer, default=0)
    profile_color: str = Column(String(8), nullable=True)
    cpge: int = Column(BigInteger, ForeignKey("cpge.id", ondelete="SET NULL"), nullable=True)
    postcpge: int = Column(BigInteger, ForeignKey("postcpge.id", ondelete="SET NULL"), nullable=True)
    generation: int = Column(Integer, nullable=True)

    def __repr__(self):
        return f"Member(id={self.id}, name={self.name}, role={self.role})"

class SchoolModel(Base):
    __tablename__ = "schools"
    __table_args__ = (
        ForeignKeyConstraint(
            ("referent", "guild"),
            ("members.id", "members.guild_id"),
            ondelete="SET NULL",
            name="schools_referent_guild_fkey",
        ),
    )
    id: int = Column(BigInteger, primary_key=True, autoincrement=True)
    name: str = Column(String(255), unique=True)
    channel: int = Column(BigInteger, nullable=False)
    guild: int = Column(BigInteger, ForeignKey("guilds.id", ondelete="RESTRICT"), nullable=False)
    referent: int = Column(BigInteger, nullable=True)
    type: str = Column(String(255), nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": "schools",
        "polymorphic_on": type
    }
    
class CPGEModel(SchoolModel):
    __tablename__ = "cpge"
    id = Column(BigInteger, ForeignKey("schools.id"), primary_key=True)

    __mapper_args__ = {
        "polymorphic_identity": "CPGE"
    }
    
class PostCPGEModel(SchoolModel):
    __tablename__ = "postcpge"
    id = Column(BigInteger, ForeignKey("schools.id"), primary_key=True)

    __mapper_args__ = {
        "polymorphic_identity": "PostCPGE"
    }

class SuggestionModel(Base):
    __tablename__ = "suggestions"

    id: int = Column(BigInteger, primary_key=True, autoincrement=True)
    author_id: int = Column(BigInteger)
    guild_id: int = Column(BigInteger, ForeignKey("guilds.id", ondelete="CASCADE"))
    date = Column(DateTime, nullable=True)
    message_id: int = Column(BigInteger, nullable=True, unique=True)
    state: str = Column(String(50), nullable=False, default="open")
    title: str = Column(String(80))
    description: str = Column(String(3072))
    handled_by: int = Column(BigInteger)
    handled_time = Column(DateTime, nullable=True)

    def __repr__(self):
        return (
            f"Suggestion(author={self.author_id}, title={self.title:30.30}"
        )


class SanctionModel(Base):
    __tablename__ = "sanctions"
    __table_args__ = (
        ForeignKeyConstraint(
            ("to_id", "guild_id"),
            ("members.id", "members.guild_id"),
            ondelete="CASCADE",
            name="sanctions_to_id_guild_id_fkey",
        ),
    )
    id: int = Column(BigInteger, primary_key=True, autoincrement=True)
    by_id: int = Column(BigInteger)
    to_id: int = Column(BigInteger)
    guild_id: int = Column(BigInteger, ForeignKey("guilds.id", ondelete="CASCADE"))
    date = Column(DateTime)
    type: str = Column(String(50))
    duration = Column(BigInteger, nullable=True)
    reason: str = Column(Text, nullable=True)

    def __repr__(self):
        return (
            f"Sanction(by={self.by_id}, to={self.to_id}, type={self.type}"
            f"duration={self.duration}, description={f'{self.reason:30.30}' if self.reason else ''})"
        )

    @property
    def get_duration(self) -> Optional[str]:
        duration = self.duration
        if not duration:
            return None
        return humanize.naturaldelta(timedelta(seconds=duration))
