from typing import Any, Optional

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class GuildModel(Base):
    """
    Represent a discord Guild
    """

    __tablename__ = "guilds"

    guild_id: Mapped[int] = mapped_column(
        BigInteger(),
        primary_key=True,
        nullable=False,
        info=dict(
            label="Guild ID",
            hint="Unique discord ID of the guild.",
        ),
    )

    roles_message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger(),
        nullable=True,
        default=None,
        info=dict(
            label="Roles Message ID",
            hint="Unique roles message ID of the guild.",
        ),
    )

    suggestion_message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger(),
        nullable=True,
        default=None,
        info=dict(
            label="Suggestion Message ID",
            hint="Unique suggestion message ID of the guild.",
        ),
    )

    def __eq__(self, other: Any) -> bool:
        """
        Check if an object is equal to the Guild

        Parameters
        ----------
        other : Any
            other object to compare

        Returns
        -------
        bool
            True if the two objects are equal, False otherwise
        """
        return isinstance(other, GuildModel) and self.guild_id == other.guild_id
