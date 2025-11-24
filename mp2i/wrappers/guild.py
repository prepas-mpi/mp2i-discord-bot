import logging
from typing import Any, List, Optional, TypeVar

import discord
from sqlalchemy import Result, delete, insert, select, update

import mp2i.database.executor as database_executor
from mp2i.database.exceptions import InsertException, ReturningElementException
from mp2i.database.models.guild import GuildModel
from mp2i.utils.config import get_config_deep

from . import ObjectWrapper

logger: logging.Logger = logging.getLogger(__name__)

T = TypeVar("T")


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

    def _update(self, **kwargs: Any) -> None:
        """
        Update GuildModel in database

        Parameters
        ----------
        kwargs : Any
            dictionnary with attributes to update, e.g. suggestions_message_id=None
        """
        result: Optional[Result[GuildModel]] = database_executor.execute(
            update(GuildModel)
            .where(
                GuildModel.guild_id == self._boxed.id,
            )
            .values(**kwargs)
            .returning(GuildModel)
        )
        if not result or not (guild_model := result.scalar_one_or_none()):
            logger.fatal(
                "Could not retrieve back MemberModel after updated from member: %d",
                self._boxed.id,
            )
        else:
            self.__model = guild_model

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

    def mapping_roles(self, roles: List[str]) -> List[discord.Role]:
        config_roles: dict[str, Any] = self._config.get("roles", {})
        out = []
        for role in roles:
            id: Optional[int] = config_roles.get(role, {}).get("id", None)
            if not id:
                logger.warning(
                    "There is no role named %s in config file for guild %d.",
                    role,
                    self._boxed.id,
                )
                continue
            if discord_role := self._boxed.get_role(id):
                out.append(discord_role)
            else:
                logger.warning(
                    "There is no role of id %d in guild %d.", id, self._boxed.id
                )
        return out

    def get_any_channel(self, id: Optional[int], type: type[T]) -> Optional[T]:
        if not id:
            return None
        channel: Optional[discord.guild.GuildChannel | discord.Thread] = (
            self._boxed.get_channel_or_thread(id)
        )
        if not channel or not isinstance(channel, type):
            return None
        return channel

    @property
    def log_channel(self) -> Optional[discord.TextChannel]:
        channel: Optional[discord.TextChannel] = self.get_any_channel(
            self._config.get("logs", {}).get("channel", None), discord.TextChannel
        )
        if not channel:
            logger.warning(
                "Log channel for guild %d has been misconfigured.", self._boxed.id
            )
        return channel

    @property
    def blacklisted_log_channels(self) -> List[int]:
        return self._config.get("logs", {}).get("blacklist", [])

    @property
    def sanctions_channel(self) -> Optional[discord.TextChannel]:
        channel: Optional[discord.TextChannel] = self.get_any_channel(
            self._config.get("sanctions", {}).get("channel", None), discord.TextChannel
        )
        if not channel:
            logger.warning(
                "Sanction channel for guild %d has been misconfigured.", self._boxed.id
            )
        return channel

    @property
    def ticket_channel(self) -> Optional[discord.TextChannel]:
        channel: Optional[discord.TextChannel] = self.get_any_channel(
            self._config.get("tickets", {}).get("channel", None), discord.TextChannel
        )
        if not channel:
            logger.warning(
                "Ticket channel for guild %d has been misconfigured.", self._boxed.id
            )
        return channel

    @property
    def max_ticket(self) -> int:
        return self._config.get("tickets", {}).get("max", 0)

    @property
    def max_promotions(self) -> int:
        return self._config.get("promotions", {}).get("max", 0)

    @property
    def suggestions_channel(self) -> Optional[discord.TextChannel]:
        """
        Get the suggestions channel

        Parameters
        ----------
        Optional[discord.TextChannel]
            The text channel can be None if not found
        """
        channel: Optional[discord.TextChannel] = self.get_any_channel(
            self._config.get("suggestions", {}).get("channel", None),
            discord.TextChannel,
        )
        if not channel:
            logger.warning(
                "Suggestions channel for guild %d has been misconfigured.",
                self._boxed.id,
            )
        return channel

    @property
    async def suggestions_message(self) -> Optional[discord.Message]:
        """
        Get the main message for suggestions

        Parameters
        ----------
        Optional[discord.Message]
            The main message for suggestions can be None if not found
        """
        channel: Optional[discord.TextChannel] = self.suggestions_channel
        if not channel or not self.__model or not self.__model.suggestion_message_id:
            return None
        return await channel.fetch_message(self.__model.suggestion_message_id)

    @suggestions_message.setter
    def suggestions_message(self, message: Optional[discord.Message]) -> None:
        """
        Change suggestions' main message id

        Parameters
        ----------
        message : Optional[discord.Message]
            The message, can be None to unset the value
        """
        if not self.__model:
            return
        self.__model.suggestion_message_id = message.id if message else None
        self._update(suggestion_message_id=self.__model.suggestion_message_id)

    @property
    def roles_message_id(self) -> Optional[int]:
        """
        Get the id of the message observed for roles

        Parameters
        ----------
        Optional[int]
            The id of the message observed for roles can be None if not set
        """
        if not self.__model:
            return -1
        return self.__model.roles_message_id

    @roles_message_id.setter
    def roles_message_id(self, id: Optional[int]) -> None:
        """
        Change id of the message observed for roles

        Parameters
        ----------
        message : Optional[int]
            The id of the message, can be None to unset the value
        """
        if not self.__model:
            return
        self.__model.roles_message_id = id
        self._update(roles_message_id=self.__model.roles_message_id)

    @property
    def selectionnable_roles(self) -> dict[str, tuple[discord.Role, int]]:
        result: dict[str, tuple[discord.Role, int]] = {}
        for role_name in self._config.get("roles", []):
            if (
                not self._config.get("roles", {})
                .get(role_name, {})
                .get("selectable", False)
            ):
                continue
            role_id: int = (
                self._config.get("roles", {}).get(role_name, {}).get("id", None)
            )
            if not role_id:
                continue
            role: Optional[discord.Role] = self._boxed.get_role(role_id)
            if not role:
                continue
            result[role_name] = (
                role,
                self._config.get("roles", {}).get(role_name, {}).get("emoji_id", 0),
            )
        return result

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
