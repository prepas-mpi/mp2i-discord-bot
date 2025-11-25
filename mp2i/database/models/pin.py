from enum import Enum as PyEnum

from sqlalchemy import (
    VARCHAR,
    BigInteger,
    Enum,
    ForeignKey,
    Sequence,
)
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class PinStatus(PyEnum):
    TODO = "TODO"
    DONE = "DONE"


class PinModel(Base):
    __tablename__ = "pins"

    pin_id: Mapped[int] = mapped_column(
        BigInteger(),
        Sequence("pin_id_seq"),
        primary_key=True,
        nullable=False,
        info=dict(label="Pin's id", hint="The unique id of the pin"),
    )

    guild_id: Mapped[int] = mapped_column(
        BigInteger(),
        ForeignKey("guilds.guild_id", name="fk_pin_guild_id", ondelete="CASCADE"),
        nullable=False,
        info=dict(label="Guild ID", hint="The unique guild id"),
    )

    original_message_id: Mapped[int] = mapped_column(
        BigInteger(),
        nullable=False,
        info=dict(label="Message ID", hint="The unique pin's message id"),
    )

    first_words: Mapped[str] = mapped_column(
        VARCHAR(255),
        nullable=False,
        info=dict(label="First words", hint="Message first words"),
    )

    alert_message_id: Mapped[int] = mapped_column(
        BigInteger(),
        nullable=False,
        info=dict(label="Alert Message ID", hint="The unique pin's alert message id"),
    )

    pin_status: Mapped[PinStatus] = mapped_column(
        Enum(PinStatus),
        nullable=False,
        default=PinStatus.TODO,
        info=dict(label="Pin Status", hint="The status of the pin"),
    )
