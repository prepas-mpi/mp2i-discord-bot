import logging
from typing import Any, List, Optional

import discord
from sqlalchemy import Result, insert, select, update

import mp2i.database.executor as database_executor
from mp2i.database.exceptions import InsertException, ReturningElementException
from mp2i.database.models.member import MemberModel
from mp2i.database.models.promotion import PromotionModel
from mp2i.database.models.ticket import TicketModel

from . import ObjectWrapper
from .user import UserWrapper

logger: logging.Logger = logging.getLogger(__name__)


class MemberWrapper(ObjectWrapper[discord.Member]):
    """
    Wrap a discord.Member object to have also its database information
    """

    def __init__(self, member: discord.Member) -> None:
        """
        Getting model if exists in database

        Parameters
        ----------
        member : discord.Member
            The member to wrap
        """
        super().__init__(member)
        self.__model = self._fetch()

    def _fetch(self) -> Optional[MemberModel]:
        """
        Fetch member's data from database

        Returns
        -------
        Optional[MemberModel]
            MemberModel with member's data if they exists in database, None otherwise
        """
        result: Optional[Result[MemberModel]] = database_executor.execute(
            select(MemberModel).where(
                MemberModel.user_id == self._boxed.id,
                MemberModel.guild_id == self._boxed.guild.id,
            )
        )
        return result.scalar() if result else None

    def _update(self, **kwargs: Any) -> None:
        """
        Update MemberModel in database

        Parameters
        ----------
        kwargs : Any
            dictionnary with attributes to update, e.g. message_count=2
        """
        result: Optional[Result[MemberModel]] = database_executor.execute(
            update(MemberModel)
            .where(
                MemberModel.user_id == self._boxed.id,
                MemberModel.guild_id == self._boxed.guild.id,
            )
            .values(**kwargs)
            .returning(MemberModel)
        )
        if not result or not (member_model := result.scalar_one_or_none()):
            logger.fatal(
                "Could not retrieve back MemberModel after updated from member: %d",
                self._boxed.id,
            )
        else:
            self.__model = member_model

    def register(self) -> MemberModel:
        """
        Register a member in database

        Returns
        -------
        MemberModel
            Newly create MemberModel if no member was found, MemberModel in database otherwise
        """
        if self.__model:
            return self.__model

        UserWrapper(self._boxed._user).register()

        result: Optional[Result[MemberModel]] = database_executor.execute(
            insert(MemberModel)
            .values(
                user_id=self._boxed.id,
                guild_id=self._boxed.guild.id,
            )
            .returning(MemberModel)
        )

        if not result:
            raise InsertException("member")

        if not (member_model := result.scalar_one_or_none()):
            raise ReturningElementException("member")

        self.__model = member_model
        return member_model

    @property
    def as_model(self) -> Optional[MemberModel]:
        return self.__model

    @property
    def member_id(self) -> int:
        if not self.__model:
            return -1
        return self.__model.member_id

    @property
    def message_count(self) -> int:
        """
        Get the message's number of the member

        Returns
        -------
        int
            the number of messages sent by the member
        """
        if not self.__model:
            return -1
        return self.__model.message_count

    def message_count_increment(self) -> None:
        """
        Increment number of messages sent by the member
        """
        if not self.__model:
            return
        self._update(message_count=self.__model.message_count + 1)

    @property
    def profile_colour(self) -> Optional[int]:
        """
        Get member's profile colour

        Returns
        -------
        Optional[int]
            Member's profile colour if it has been set, None otherwise
        """
        if not self.__model:
            return None
        return self.__model.profile_colour

    @profile_colour.setter
    def profile_colour(self, colour: Optional[int]) -> None:
        if not self.__model:
            return
        self.__model.profile_colour = colour
        self._update(profile_colour=colour)

    @property
    def tickets(self) -> List[TicketModel]:
        if not self.__model:
            return []
        return self.__model.tickets

    @property
    def promotions(self) -> List[PromotionModel]:
        if not self.__model:
            return []
        return self.__model.promotions

    def __eq__(self, value: Any) -> bool:
        """
        Check if an object is equal to the MemberWrapper

        Parameters
        ----------
        other : Any
            other object to compare

        Returns
        -------
        bool
            True if the two objects are equal, False otherwise
        """
        if not isinstance(value, MemberWrapper):
            return False

        if not value.__model or not self.__model:
            return False

        return self.__model == value.__model
