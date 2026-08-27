from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, Sequence, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mp2i.database.models.school import SchoolModel

from . import Base


class PromotionModel(Base):
    """
    A represent a member in a school
    """

    __tablename__ = "promotions"
    __tableargs__ = (
        UniqueConstraint(
            "school_id", "member_id", name="promotions_school_member_cstrnt"
        ),
    )

    promotion_id: Mapped[int] = mapped_column(
        BigInteger(),
        Sequence("promotion_id_seq"),
        primary_key=True,
        nullable=False,
        info=dict(label="Promotion ID", hint="Unique promotion's id"),
    )

    school_id: Mapped[int] = mapped_column(
        BigInteger(),
        ForeignKey(
            "schools.school_id", name="fk_promotion_school_id", ondelete="CASCADE"
        ),
        nullable=False,
        info=(dict(label="School ID", hint="School's id")),
    )

    member_id: Mapped[int] = mapped_column(
        BigInteger(),
        ForeignKey(
            "members.member_id", name="fk_promotion_member_id", ondelete="CASCADE"
        ),
        nullable=False,
        info=dict(label="Referent ID", hint="Member's id"),
    )

    entry_year: Mapped[Optional[int]] = mapped_column(
        BigInteger(),
        nullable=True,
        default=None,
        info=dict(
            label="Entry year", hint="Year in which the member joined the school"
        ),
    )

    exit_year: Mapped[Optional[int]] = mapped_column(
        BigInteger(),
        nullable=True,
        default=None,
        info=dict(
            label="Promotion year", hint="Year in which the member left the school"
        ),
    )

    school: Mapped[SchoolModel] = relationship("SchoolModel", lazy="selectin")
