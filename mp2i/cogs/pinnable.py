from datetime import datetime

import discord
from discord.ext.commands import Cog, guild_only

from mp2i.wrappers.guild import GuildWrapper


class Pinnable(Cog):

    MINIMUM_PINS = 5

    def __init__(self, bot):
        self.bot = bot

    @Cog.listener("on_raw_reaction_add")
    @guild_only()
    async def add_pin(self, payload) -> None:
        """
        Add a pin to a message and send it to website channel when
        it reach the required number of pins reactions.
        """
        if str(payload.emoji) != "📌":
            return

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        pins = discord.utils.get(message.reactions, emoji="📌", me=False)
        if pins is None or pins.count < self.MINIMUM_PINS:
            return

        author = message.author
        embed = discord.Embed(
            colour=0x00FF00,
            title="Message épinglé",
            description="Un message a été retenu par la communauté, vous pouvez "
                        "probablement l'ajouter dans la [FAQ](https://prepas-mp2i.org/faq/).",
            timestamp=datetime.now(),
        )
        embed.add_field(name="Lien du message", value=message.jump_url)
        embed.set_author(name=author.name, icon_url=author.avatar.url)
        embed.set_footer(text=self.bot.user.name)
        website_chan = self.bot.get_channel(
            GuildWrapper(channel.guild).config.channels.website
        )
        await website_chan.send(embed=embed)
        # Pour ne pas envoyer le message plusieurs fois
        await message.add_reaction("📌")


async def setup(bot) -> None:
    await bot.add_cog(Pinnable(bot))