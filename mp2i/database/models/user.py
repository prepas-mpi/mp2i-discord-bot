from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class User(Base):
    """
    Represent a discord User
    """

    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(
        BigInteger(),
        primary_key=True,
        nullable=False,
        info=dict(
            label="User ID",
            hint="Unique discord ID of the user.",
        ),
    )
