from typing import Any

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class UserModel(Base):
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

    def __eq__(self, other: Any) -> bool:
        """
        Check if an object is equal to the User

        Parameters
        ----------
        other : Any
            other object to compare

        Returns
        -------
        bool
            True if the two objects are equal, False otherwise
        """
        return isinstance(other, UserModel) and self.user_id == other.user_id
