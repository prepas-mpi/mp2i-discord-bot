import logging
import re
from typing import List, Optional, Sequence

import discord
from discord.ext.commands import Bot, Cog, Context, guild_only, hybrid_command
from sqlalchemy import Result
from sqlalchemy.sql import select

import mp2i.database.executor as database_executor
from mp2i.database.models.member import MemberModel
from mp2i.utils.paginator import EmbedPaginator
from mp2i.wrappers.member import MemberWrapper

logger: logging.Logger = logging.getLogger(__name__)


class Leaderboard(Cog):
    """
    Leaderboard utilities
    """

    __ENTRY_FORMAT: str = "{place}. **{name}** : {messages} messages"
    __NAME_PATTERN: re.Pattern = re.compile(r"([^|@]+)([@|#]):?[^@#|]*")
    __ENTRIES_PER_PAGE: int = 10

    @Cog.listener("on_message")
    @guild_only()
    async def update_message_counter(self, message: discord.Message) -> None:
        """
        Update the message counter of the author

        Parameters
        ----------
        message : discord.Message
            Sent message by the member
        """
        if not isinstance(message.author, discord.Member) or message.author.bot:
            return
        # update member's messages count when receive a message from they
        MemberWrapper(message.author).message_count_increment()

    @hybrid_command(
        name="leaderboard",
        description="Afficher le classement du nombre de messages",
    )
    @guild_only()
    async def show_leaderboard(self, ctx: Context) -> None:
        """
        Send the current leaderboard of all members

        Parameters
        ----------
        ctx : Context
            The context of the slashcommand
        """
        if not ctx.interaction:
            logger.fatal("Leaderboard command should not have an empty interaction.")
            await ctx.reply(
                "Une erreur est survenue. Merci de contacter un responsable Bot.",
                ephemeral=True,
            )
            return

        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            logger.fatal("Leaderboard command should not have an empty guild")
            await ctx.reply(
                "Une erreur est survenue. Merci de contacter un responsable Bot.",
                ephemeral=True,
            )
            return

        await ctx.defer()

        # get all members
        result: Optional[Result[MemberModel]] = database_executor.execute(
            select(MemberModel)
            .where(
                MemberModel.guild_id == ctx.guild.id,
                MemberModel.presence,
                MemberModel.message_count > 0,
            )
            .order_by(MemberModel.message_count.desc(), MemberModel.display_name.asc())
        )

        if not result:
            await ctx.reply(
                "Impossible de contacter la base de données.", ephemeral=True
            )
            return

        sorted_members: Sequence[MemberModel] = result.scalars().all()

        if len(sorted_members) == 0:
            await ctx.reply(
                "Aucun membre pouvant être classé n'a été trouvé sur le serveur.",
                ephemeral=True,
            )
            return

        # save interaction's author information
        author: MemberWrapper = MemberWrapper(ctx.author)
        author_index: int = -1
        author_name: str = author.display_name

        entries: List[str] = []
        # enumerate all members from first to the last
        for index, member in enumerate(sorted_members):
            name: str = member.display_name
            if match := self.__NAME_PATTERN.match(name):
                name = match.group(1)
            if member.member_id == author.member_id:
                author_index = index
                author_name = name
            entries.append(
                self.__ENTRY_FORMAT.format(
                    place=index + 1, name=name, messages=member.message_count
                )
            )

        header: str = " > "
        if author_index == -1:
            header += "Vous n'êtes pas classé."
        else:
            header += self.__ENTRY_FORMAT.format(
                place=author_index + 1,
                name=author_name,
                messages=author.message_count,
            )

        # we are sure that there are at least one member
        first_member: MemberWrapper = sorted_members[0]
        # get colour of the first member
        colour: Optional[int] = first_member.profile_colour
        if not colour and (colour_member := ctx.guild.get_member(first_member.user_id)):
            colour = colour_member.colour.value

        embed_paginator: EmbedPaginator = EmbedPaginator(
            author=ctx.author.id,
            title="Top des membres du serveur",
            header=header,
            entries=entries,
            colour=colour or 0,
        )

        await embed_paginator.send(ctx.interaction)


async def setup(bot: Bot):
    """
    Setting up the leaderboard utilities

    Parameters
    ----------
    bot : Bot
        instance of the discord bot
    """
    await bot.add_cog(Leaderboard())
