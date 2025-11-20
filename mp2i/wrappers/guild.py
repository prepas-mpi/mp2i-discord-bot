import logging
from typing import Any, List, Optional

import discord
from sqlalchemy import Result, delete, insert, select

import mp2i.database.executor as database_executor
from mp2i.database.exceptions import InsertException, ReturningElementException
from mp2i.database.models.guild import GuildModel
from mp2i.utils.config import get_config_deep

from . import ObjectWrapper

logger: logging.Logger = logging.getLogger(__name__)


class GuildWrapper(ObjectWrapper[discord.Guild]):
    """
    Wrap a discord.Guild object to also have its database information
    """

    def __init__(self, guild: discord.Guild, fetch: bool = True) -> None:
        super().__init__(guild)
        self._config = get_config_deep(f"guilds.{guild.id}")
        if fetch:
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

    def delete(self) -> None:
        """
        Delete the guild
        """
        if not self.__model:
            return

        database_executor.execute(
            delete(GuildModel).where(GuildModel.guild_id == self.__model.guild_id)
        )

    def get_text_channel(self, id: Optional[int]) -> Optional[discord.TextChannel]:
        if not id:
            return None
        channel: Optional[discord.GuildChannel] = self._boxed.get_channel(id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return None
        return channel

    @property
    def get_log_channel(self) -> Optional[discord.TextChannel]:
        channel: Optional[discord.TextChannel] = self.get_text_channel(
            self._config.get("logs", {}).get("channel", None)
        )
        if not channel:
            logger.warning(
                "Log channel for guild %d has been misconfigured.", self._boxed.id
            )
        return channel

    @property
    def get_blacklisted_log_channels(self) -> List[int]:
        return self._config.get("logs", {}).get("blacklist", [])

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
