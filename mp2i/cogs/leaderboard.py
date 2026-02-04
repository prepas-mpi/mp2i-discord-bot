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

        # get all members asynchronously
        async def construct_member_async(member: discord.Member) -> MemberWrapper:
            return MemberWrapper(member)

        coroutines: List[Coroutine[Any, Any, MemberWrapper]] = [
            construct_member_async(m) for m in ctx.guild.members if not m.bot
        ]
        # at most 50 tasks in parallel
        semaphore: asyncio.Semaphore = asyncio.Semaphore(50)

        async def exec(coroutine: Coroutine[Any, Any, MemberWrapper]) -> MemberWrapper:
            async with semaphore:
                return await coroutine

        members_wrapper_list: List[MemberWrapper] = await asyncio.gather(
            *(exec(coroutine) for coroutine in coroutines)
        )

        # get all members that have sent at least 1 message
        members_wrapper: Iterable[MemberWrapper] = filter(
            lambda mw: mw.message_count > 0,
            [MemberWrapper(m) for m in ctx.guild.members if not m.bot],
        )

        # sort members by message or name in case of equality
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

        # we are sure that there are at least one member
        first_member: MemberWrapper = sorted_members[0]
        # get colour of the first member
        colour: Optional[int] = first_member.profile_colour or first_member.colour

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
