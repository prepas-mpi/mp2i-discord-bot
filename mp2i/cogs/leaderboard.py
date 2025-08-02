from typing import List
from operator import attrgetter
import re

from discord.ext.commands import Cog
from discord.ext.commands import (
    hybrid_command,
    guild_only,
)

from mp2i.wrappers.member import MemberWrapper
from mp2i.utils.discord import defer, EmbedPaginator

NAME_REGEX: re.Pattern = re.compile(r"([^\|@]+)(@|\||#):?[^@#\|]*")


class Leaderboard(Cog):

    def __init__(self, bot):
        self.bot = bot

    @hybrid_command(name="leaderboard")
    @guild_only()
    @defer()
    async def leaderboard(self, ctx) -> None:
        """
        Affiche le classement des membres par nombre de messages.
        """

        members: List[MemberWrapper] = [MemberWrapper(m) for m in ctx.guild.members if not m.bot]
        members.sort(key=attrgetter("messages_count"), reverse=True)
        
        author: MemberWrapper = MemberWrapper(ctx.author)
        rank: int = members.index(author) + 1
        # get author display name without school
        user_name: str = author.display_name
        if m := NAME_REGEX.match(user_name):
            user_name = m.group(1).strip()
        header: str = f"→ {rank}. **{user_name}** : {author.messages_count} messages\n\n"
        content: List[str] = []

        title = f"Top des membres du serveur"

        # retrieve each line
        for r, member in enumerate(members, 1):
            user_name: str = member.display_name
            if m := NAME_REGEX.match(user_name):
                user_name = m.group(1).strip()
            content.append(f"{r}. **{user_name}** : {member.messages_count} messages\n")

        # select colour of first's profil
        colour = int(members[0].profile_color, 16)

        # if first's profil has default colour get
        # their first coloured role's colour
        if colour == 0x0000FF:
            # reverse to get the top role
            for role in reversed(members[0].member.roles):
                # discriminate role by its string colour
                if f"{role.colour}" != "#000000":
                    colour = role.colour
                    break

        # create paginate embed
        embed = EmbedPaginator(
            title=title,
            colour=colour,
            content_header=header,
            content_body=content,
            nb_by_pages=10,
            footer="",
            author_id=ctx.author.id,
            timeout=500,
        )

        await embed.send(ctx)

async def setup(bot) -> None:
    await bot.add_cog(Leaderboard(bot))
