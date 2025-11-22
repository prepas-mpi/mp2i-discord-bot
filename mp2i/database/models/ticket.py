from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Integer, Sequence
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class TicketLevel(PyEnum):
    ADMINISTRATOR = 0
    MODERATOR = 1


class TicketModel(Base):
    """
    Represent a Ticket
    """

    __tablename__ = "tickets"
    __table_args__ = (
        Index("idx_ticket_member", "member_id"),
        Index("idx_ticket_thread", "thread_id"),
    )

    ticket_id: Mapped[int] = mapped_column(
        BigInteger(),
        Sequence("ticket_id_seq"),
        primary_key=True,
        nullable=False,
        info=dict(label="Ticket ID", hint="Unique ticket ID in database."),
    )

    member_id: Mapped[int] = mapped_column(
        BigInteger(),
        ForeignKey("members.member_id", name="fk_ticket_member_id", ondelete="CASCADE"),
        nullable=False,
        info=dict(label="Member ID", hint="Unique member ID in database."),
    )

    thread_id: Mapped[int] = mapped_column(
        BigInteger(),
        nullable=False,
        info=dict(label="Thread ID", hint="Thread's id linked to the ticket."),
    )

    level: Mapped[TicketLevel] = mapped_column(
        Enum(TicketLevel),
        nullable=False,
        info=dict(
            label="Ticket Level",
            hint="Level of the ticket (administrator, moderator).",
        ),
    )

    closed: Mapped[bool] = mapped_column(
        Integer(),
        nullable=False,
        default=False,
        info=dict(label="Ticket Closed", hint="Tell if ticket is closed or not"),
    )

    def __eq__(self, other: Any) -> bool:
        """
        Check if an object is equal to the Member

        Parameters
        ----------
        other : Any
            other object to compare

        Returns
        -------
        bool
            True if the two objects are equal, False otherwise
        """
        return isinstance(other, TicketModel) and self.ticket_id == other.ticket_id
