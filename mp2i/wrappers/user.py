import logging
from typing import Any, Optional

import discord
from sqlalchemy import Result, insert, select

import mp2i.database.executor as database_executor
from mp2i.database.exceptions import InsertException, ReturningElementException
from mp2i.database.models.user import User as UserModel

from . import ObjectWrapper

logger: logging.Logger = logging.getLogger(__name__)


class UserWrapper(ObjectWrapper[discord.User]):
    """
    Wrap a discord.User object to have also its database information
    """

    def __init__(self, user: discord.User) -> None:
        """
        Getting model if exists in database

        Parameters
        ----------
        user : discord.User
            The user to wrap
        """
        super().__init__(user)
        self.__model = self._fetch()

    def _fetch(self) -> Optional[UserModel]:
        """
        Fetch user's data from database

        Returns
        -------
        Optional[UserModel]
            UserModel with user's data if they exists in database, None otherwise
        """
        result: Optional[Result[UserModel]] = database_executor.execute(
            select(UserModel).where(UserModel.user_id == self._boxed.id)
        )
        return result.scalar_one_or_none() if result else None

    def register(self) -> UserModel:
        """
        Register a user in database

        Returns
        -------
        UserModel
            Newly create UserModel if no user was found, UserModel in database otherwise
        """
        if self.__model:
            return self.__model
        result: Optional[Result[UserModel]] = database_executor.execute(
            insert(UserModel)
            .values(
                user_id=self._boxed.id,
            )
            .returning(UserModel)
        )

        if not result:
            raise InsertException("user")

        if not (user_model := result.scalar_one_or_none()):
            raise ReturningElementException("user")

        self.__model = user_model
        return user_model

    def __eq__(self, value: Any) -> bool:
        """
        Check if an object is equal to the UserWrapper

        Parameters
        ----------
        other : Any
            other object to compare

        Returns
        -------
        bool
            True if the two objects are equal, False otherwise
        """
        if not isinstance(value, UserWrapper):
            return False

        if not value.__model or not self.__model:
            return False

        return self.__model == value.__model
