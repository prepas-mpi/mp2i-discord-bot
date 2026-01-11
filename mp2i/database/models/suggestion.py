import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import VARCHAR, BigInteger, DateTime, Enum, ForeignKey, Sequence
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class SuggestionStatus(PyEnum):
    OPEN = ("\ud83d\udd51", 0x4286F4)
    CLOSED = ("📦", 0xA2D2FF)
    ACCEPTED = ("✅", 0x1FC622)
    REJECTED = ("❌", 0xFF6B60)

    @property
    def emote(self) -> str:
        return self.value[0]

    @property
    def colour(self) -> int:
        return self.value[1]

    @property
    def result(self) -> str:
        if self == SuggestionStatus.CLOSED:
            return "fermée"
        elif self == SuggestionStatus.ACCEPTED:
            return "acceptée"
        elif self == SuggestionStatus.REJECTED:
            return "rejetée"
        return "ouverte"


class SuggestionModel(Base):
    """
    Represent a suggestion
    """

    __tablename__ = "suggestions"

    suggestion_id: Mapped[int] = mapped_column(
        BigInteger(),
        Sequence("suggestion_id_seq"),
        primary_key=True,
        nullable=False,
        info=(dict(label="Suggestion ID", hint="Unique suggestion ID")),
    )

    guild_id: Mapped[int] = mapped_column(
        BigInteger(),
        ForeignKey("guilds.guild_id", name="fk_guild_guild_id", ondelete="CASCADE"),
        nullable=False,
        info=dict(label="Guild ID", hint="Unique guild ID"),
    )

    author_id: Mapped[Optional[int]] = mapped_column(
        BigInteger(),
        ForeignKey(
            "members.member_id", name="fk_suggestion_author_id", ondelete="SET NULL"
        ),
        nullable=True,
        info=dict(label="Author ID", hint="Unique author id"),
    )

    suggestion_title: Mapped[str] = mapped_column(
        VARCHAR(255),
        nullable=False,
        info=dict(label="Suggestion Title", hint="The title of the suggestion"),
    )

    suggestion_description: Mapped[str] = mapped_column(
        VARCHAR(3072),
        nullable=False,
        info=dict(
            label="Suggestion Description", hint="The description of the suggestion"
        ),
    )

    suggestion_status: Mapped[SuggestionStatus] = mapped_column(
        Enum(SuggestionStatus),
        nullable=False,
        default=SuggestionStatus.OPEN,
        info=dict(label="Suggestion Status", hint="The status of the suggestion"),
    )

    suggestion_date: Mapped[datetime.datetime] = mapped_column(
        DateTime(),
        nullable=False,
        default=datetime.datetime.now(),
        info=dict(label="Suggestion's date", hint="Date of the suggestion"),
    )

    suggestion_message: Mapped[int] = mapped_column(
        BigInteger(),
        nullable=False,
        info=dict(label="Suggestion's message", hint="Message's id of the suggestion"),
    )

    staff_id: Mapped[Optional[int]] = mapped_column(
        BigInteger(),
        ForeignKey(
            "members.member_id", name="fk_suggestion_staff_id", ondelete="SET NULL"
        ),
        nullable=True,
        default=None,
        info=dict(
            label="Suggestion Status", hint="The staff that closed the suggestion"
        ),
    )

    staff_description: Mapped[Optional[str]] = mapped_column(
        VARCHAR(500),
        nullable=True,
        default=None,
        info=dict(
            label="Suggestion Staff Description",
            hint="The the answer to the suggestion",
        ),
    )

    suggestion_handled_date: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(),
        nullable=True,
        default=None,
        info=dict(label="Suggestion handle's date", hint="Date of the handle of the suggestion"),
    )
