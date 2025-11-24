from sqlalchemy import (
    VARCHAR,
    BigInteger,
    ForeignKey,
    Sequence,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class AcademyModel(Base):
    """
    Represent an Academy
    """

    __tablename__ = "academies"
    __tableargs__ = (
        UniqueConstraint("academy_name"),
        UniqueConstraint("domain_name"),
    )

    academy_id: Mapped[int] = mapped_column(
        BigInteger(),
        Sequence("academy_id_seq"),
        primary_key=True,
        nullable=False,
        info=dict(label="Academy ID", hint="Unique academy ID in database."),
    )

    guild_id: Mapped[int] = mapped_column(
        BigInteger(),
        ForeignKey("guilds.guild_id", name="fk_academy_guild_id", ondelete="CASCADE"),
        nullable=False,
        info=dict(label="Guild ID", hint="Unique guild ID in database."),
    )

    academy_name: Mapped[str] = mapped_column(
        VARCHAR(255),
        nullable=False,
        info=dict(label="Academy Name", hint="Name of the academy"),
    )

    domain_name: Mapped[str] = mapped_column(
        VARCHAR(255),
        nullable=False,
        info=dict(label="Domain Name", hint="Domain name used by the academy"),
    )
