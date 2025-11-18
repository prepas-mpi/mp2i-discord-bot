from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Guild(Base):
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
