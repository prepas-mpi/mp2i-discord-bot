from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Member(Base):
    """
    Represent a discord Guild Member
    """

    __tablename__ = "members"
    __table_args__ = (PrimaryKeyConstraint("guild_id", "user_id"),)

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
