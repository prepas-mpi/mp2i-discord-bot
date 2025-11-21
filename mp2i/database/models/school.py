from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import VARCHAR, BigInteger, Enum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .member import MemberModel
else:
    MemberModel = "MemberModel"


class SchoolType(PyEnum):
    """
    Enumeration of SchoolType
    """

    CPGE = "CPGE"
    ECOLE = "ECOLE"


class SchoolModel(Base):
    """
    Represent a School
    """

    __tablename__ = "schools"
    __tableargs__ = (Index("idx_school_name", "school_name"),)

    school_id: Mapped[int] = mapped_column(
        BigInteger(),
        primary_key=True,
        nullable=False,
        info=(dict(label="School ID", hint="Unique school ID")),
    )

    guild_id: Mapped[int] = mapped_column(
        BigInteger(),
        ForeignKey("guilds.guild_id", name="fk_school_guild_id", ondelete="CASCADE"),
        nullable=False,
        info=dict(label="Guild ID", hint="Unique guild ID"),
    )

    school_name: Mapped[str] = mapped_column(
        VARCHAR(255),
        unique=True,
        nullable=False,
        info=dict(label="School Name", hint="Name of the school"),
    )

    school_type: Mapped[SchoolType] = mapped_column(
        Enum(SchoolType),
        nullable=False,
        info=dict(label="School Type", hint="Type of the school (CPGE, ECOLE)"),
    )

    thread_id: Mapped[Optional[int]] = mapped_column(
        BigInteger(),
        nullable=True,
        default=None,
        info=dict(label="Thread ID", hint="Thread use to discuss about the school"),
    )

    referent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger(),
        ForeignKey(
            "members.member_id", name="fk_school_member_id", ondelete="SET NULL"
        ),
        nullable=True,
        default=None,
        info=dict(label="Referent ID", hint="Member's id of the school referent"),
    )

    referent: Mapped[Optional[MemberModel]] = relationship(
        "MemberModel", lazy="selectin"
    )

    def __repr__(self) -> str:
        return "School(school_name={name},)".format(name=self.school_name)

    def __eq__(self, value: Any) -> bool:
        """
        Check if an object is equal to the SchoolModel

        Parameters
        ----------
        other : Any
            other object to compare

        Returns
        -------
        bool
            True if the two objects are equal, False otherwise
        """
        return isinstance(value, SchoolModel) and self.school_id == value.school_id
