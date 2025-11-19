import logging
import re
from typing import Iterable, List, Optional

import discord
from discord.ext.commands import Bot, Cog, Context, guild_only, hybrid_command

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

    def __init__(self, bot: Bot) -> None:
        """ """
        self.bot = bot

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

        members_wrapper: Iterable[MemberWrapper] = filter(
            lambda mw: mw.message_count > 0,
            [MemberWrapper(m) for m in ctx.guild.members if not m.bot],
        )

        sorted_members: List[MemberWrapper] = sorted(
            members_wrapper,
            key=lambda m: (m.message_count, m.display_name),
            reverse=True,
        )

        if len(sorted_members) == 0:
            await ctx.reply(
                "Aucun membre pouvant être classé n'a été trouvé sur le serveur.",
                ephemeral=True,
            )
            return

        author: MemberWrapper = MemberWrapper(ctx.author)
        author_index: int = -1
        author_name: str = author.display_name

        entries: List[str] = []
        for index, member in enumerate(sorted_members):
            name: str = member.display_name
            if match := self.__NAME_PATTERN.match(name):
                name = match.group(1)
            if member == author:
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

        first_member: MemberWrapper = sorted_members[0]
        colour: Optional[int] = first_member.profile_colour
        if not colour:
            for role in reversed(first_member.roles):
                if f"{role.colour}" != "#000000":
                    colour = role.colour
                    break

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
    await bot.add_cog(Leaderboard(bot))
