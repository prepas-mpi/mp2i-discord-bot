import logging
from typing import Any, Optional

import discord
from sqlalchemy import Result, insert, select

import mp2i.database.executor as database_executor
from mp2i.database.exceptions import InsertException, ReturningElementException
from mp2i.database.models.guild import Guild as GuildModel

from . import ObjectWrapper

logger: logging.Logger = logging.getLogger(__name__)


class GuildWrapper(ObjectWrapper[discord.Guild]):
    """
    Wrap a discord.Guild object to also have its database information
    """

    def __init__(self, guild: discord.Guild) -> None:
        super().__init__(guild)
        self.__model = self._fetch()

    def _fetch(self) -> Optional[GuildModel]:
        """
        Fetch guild's data from database

        Returns
        -------
        Optional[GuildModel]
            GuildModel with guild's data if they exists in database, None otherwise
        """
        result: Optional[Result[GuildModel]] = database_executor.execute(
            select(GuildModel).where(GuildModel.guild_id == self._boxed.id)
        )
        return result.scalar_one_or_none() if result else None

    def register(self) -> GuildModel:
        """
        Register a guild in database

        Returns
        -------
        GuildModel
            Newly create GuildModel if no guild was found, GuildModel in database otherwise
        """
        if self.__model:
            return self.__model
        result: Optional[Result[GuildModel]] = database_executor.execute(
            insert(GuildModel)
            .values(
                guild_id=self._boxed.id,
            )
            .returning(GuildModel)
        )

        if not result:
            raise InsertException("guild")

        if not (guild_model := result.scalar_one_or_none()):
            raise ReturningElementException("guild")

        self.__model = guild_model
        return guild_model

    def __eq__(self, value: Any) -> bool:
        """
        Check if an object is equal to the GuildWrapper

        Parameters
        ----------
        other : Any
            other object to compare

        Returns
        -------
        bool
            True if the two objects are equal, False otherwise
        """
        if not isinstance(value, GuildWrapper):
            return False

        if not value.__model or not self.__model:
            return False

        return self.__model == value.__model
