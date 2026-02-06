from typing import Any, List, Optional

from sqlalchemy import (
    VARCHAR,
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Sequence,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mp2i.database.models.promotion import PromotionModel
from mp2i.database.models.sanction import SanctionModel
from mp2i.database.models.ticket import TicketModel

from . import Base


class MemberModel(Base):
    """
    Represent a discord Guild Member
    """

    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id"),
        Index("idx_member_guild_user", "guild_id", "user_id"),
    )

    member_id: Mapped[int] = mapped_column(
        BigInteger(),
        Sequence("member_id_seq"),
        primary_key=True,
        nullable=False,
        info=dict(label="Member ID", hint="Unique member ID in database."),
    )

    guild_id: Mapped[int] = mapped_column(
        BigInteger(),
        ForeignKey("guilds.guild_id", name="fk_member_guild_id", ondelete="CASCADE"),
        nullable=False,
        info=dict(label="Guild ID", hint="Unique discord ID of the guild."),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger(),
        ForeignKey("users.user_id", name="fk_member_user_id", ondelete="CASCADE"),
        nullable=False,
        info=dict(label="User ID", hint="Unique discord ID of the user."),
    )

    display_name: Mapped[str] = mapped_column(
        VARCHAR(127),
        nullable=False,
        default="",
        info=dict(
            label="User displayname", hint="Displayname of the user on the guild"
        ),
    )

    presence: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=False,
        info=dict(label="User presence", hint="Presence of the user on the guild"),
    )

    message_count: Mapped[int] = mapped_column(
        Integer(),
        default=0,
        nullable=False,
        info=dict(
            label="Message counter", hint="Number of messages sent by the member"
        ),
    )

    profile_colour: Mapped[Optional[int]] = mapped_column(
        Integer(),
        nullable=True,
        info=dict(label="Profile Colour", hint="Member's profile colour"),
    )

    promotions: Mapped[List[PromotionModel]] = relationship(
        "PromotionModel", lazy="selectin"
    )

    sanctions: Mapped[List[SanctionModel]] = relationship(
        "SanctionModel",
        lazy="selectin",
        foreign_keys=[SanctionModel.victim_id],
        back_populates="victim",
    )

    tickets: Mapped[List[TicketModel]] = relationship("TicketModel", lazy="selectin")

    def __eq__(self, other: Any) -> bool:
        """
        Check if an object is equal to the Member

        Parameters
        ----------
        other : Any
            other object to compare

        Returns
        -------
        bool
            True if the two objects are equal, False otherwise
        """
        return (
            isinstance(other, MemberModel)
            and self.guild_id == other.guild_id
            and self.user_id == other.user_id
        )
