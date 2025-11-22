import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    VARCHAR,
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Sequence,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .member import MemberModel
else:
    MemberModel = "MemberModel"


class SanctionType(PyEnum):
    WARN = ("WARNING", 0xFF00FF)
    TIMEOUT = ("MUTE", 0xFDAC5B)
    UNTIMEOUT = ("DEMUTE", 0xFA9C1B)
    KICK = ("KICK", 0xDD4B1A)
    BAN = ("BAN", 0xFF0000)
    UNBAN = ("DEBAN", 0xFA9C1B)

    @property
    def get_colour(self) -> int:
        return self.value[1]


class SanctionModel(Base):
    __tablename__ = "sanctions"

    sanction_id: Mapped[int] = mapped_column(
        BigInteger(),
        Sequence("sanction_id_seq"),
        primary_key=True,
        nullable=False,
        info=dict(label="Sanction ID", hint="Unique sanction id"),
    )

    guild_id: Mapped[int] = mapped_column(
        BigInteger(),
        ForeignKey("guilds.guild_id", name="fk_sanction_guild_id", ondelete="CASCADE"),
        nullable=False,
        info=dict(label="Sanction's guild", hint="Id of the guild of the sanction"),
    )

    victim_id: Mapped[int] = mapped_column(
        BigInteger(),
        ForeignKey(
            "members.member_id", name="fk_sanction_victim_id", ondelete="CASCADE"
        ),
        nullable=False,
        info=dict(label="Sanction's victim", hint="Id of the victim of the sanction"),
    )

    staff_id: Mapped[Optional[int]] = mapped_column(
        BigInteger(),
        ForeignKey(
            "members.member_id", name="fk_sanction_staff_id", ondelete="SET NULL"
        ),
        nullable=True,
        info=dict(label="Sanction's staff", hint="Id of the staff of the sanction"),
    )

    sanction_type: Mapped[SanctionType] = mapped_column(
        Enum(SanctionType),
        nullable=False,
        info=dict(label="Sanction's type", hint="Type of sanction"),
    )

    sanction_date: Mapped[datetime.datetime] = mapped_column(
        DateTime(),
        nullable=False,
        default=datetime.datetime.now(),
        info=dict(label="Sanction's date", hint="Date of the sanction"),
    )

    sanction_reason: Mapped[Optional[str]] = mapped_column(
        VARCHAR(1024),
        nullable=True,
        default=None,
        info=dict(label="Sanction's reason", hint="Reason of the sanction"),
    )

    sanction_duration: Mapped[Optional[int]] = mapped_column(
        BigInteger(),
        nullable=True,
        default=None,
        info=dict(label="Sanction's duration", hint="Duration of the sanction"),
    )

    victim: Mapped[MemberModel] = relationship(
        "MemberModel",
        foreign_keys=[victim_id],
        lazy="joined",
        back_populates="sanctions",
    )

    staff: Mapped[Optional[MemberModel]] = relationship(
        "MemberModel",
        foreign_keys=[staff_id],
        lazy="joined",
    )
