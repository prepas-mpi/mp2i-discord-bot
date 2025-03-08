import logging
from datetime import datetime

import discord
from discord import TextStyle
from discord.ext.commands import Cog, GroupCog
from discord.app_commands import Choice, choices, command
from discord.ui import Modal, TextInput
from sqlalchemy import delete, insert, select, update

from mp2i import STATIC_DIR
from mp2i.models import SuggestionModel
from mp2i.utils import database
from mp2i.wrappers.guild import GuildWrapper
from mp2i.utils.discord import defer, has_any_role

logger = logging.getLogger(__name__)

class Suggestion(GroupCog, group_name="suggestions", description="Gestion des suggestions."):
    """
    Offers commands to allow members to propose suggestions and interact with them
    """

    def __init__(self, bot):
        self.bot = bot

    async def __send_suggestions_rules(self, channel) -> None:
        """
        Affiche le fonctionnement des suggestions.
        """
        guild = GuildWrapper(channel.guild)
        if guild.suggestion_message_id:
            try:
                message = await channel.fetch_message(guild.suggestion_message_id)
                await message.delete()
            except discord.NotFound:
                logger.warning("Suggestions message's id is set but no message was found.")
        with open(STATIC_DIR / "text/suggestions.md", encoding="utf-8") as f:
            content = f.read()
        embed = discord.Embed(
            title="Fonctionnement des suggestions",
            description=content,
            colour=0xFF66FF,
            timestamp=datetime.now(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        button = discord.ui.Button(
            custom_id=f"suggestion:proposal",
            style=discord.ButtonStyle.green,
            label="Soumettre une suggestion"
        )
        view = discord.ui.View()
        view.add_item(button)

        message = await channel.send(embed=embed, view=view)
        guild.suggestion_message_id = message.id

    @Cog.listener("on_interaction")
    async def send_suggestions_modal(self, interaction: discord.Interaction) -> None:
        """
        Send a modal to submit a suggestion.
        """
        if not ("custom_id" in interaction.data.keys()) or interaction.data["custom_id"] != "suggestion:proposal":
            return
        await interaction.response.send_modal(self.SuggestionsModal(self))

    async def make_suggestion(self, title, content, channel, user) -> None:
        """
        Create suggestion message, add reactions and then create a thread.
        """
        embed = discord.Embed(
            title=title,
            description=content,
            colour=0x4286f4
        )
        if user.avatar:
            embed.set_author(name=user.name, icon_url=user.avatar.url)
        else:
            embed.set_author(name=user.name)
        embed.set_footer(text=f"\uD83D\uDD51 Suggestion non-traitée")
        embed.timestamp = datetime.now()
        msg = await channel.send(embed=embed)
        try:
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            thread = await msg.channel.create_thread(
                name=title, message=msg
            )
            await thread.add_user(user)
        except discord.errors.NotFound:
            pass
        database.execute(
            insert(SuggestionModel).values(
                author_id=msg.author.id,
                date=datetime.now(),
                guild_id=msg.guild.id,
                title=title,
                description=msg.content,
                message_id=msg.id,
                channel_id=msg.channel.id,
                state="open",
            )
        )
        await self.__send_suggestions_rules(msg.channel)


    async def close_suggestion(self, payload) -> None:
        """
        Send result to all users when an admin add a reaction.
        """
        if payload.member.bot or str(payload.emoji) not in ("✅", "❌", "🔒"):
            return
        try:
            channel = self.bot.get_channel(payload.channel_id)
            suggestion = await channel.fetch_message(payload.message_id)
        except discord.errors.NotFound:
            return
        if channel != GuildWrapper(channel.guild).suggestion_channel:
            return
        if not payload.member.guild_permissions.administrator:
            return  # only administrator can close a suggestion
        accept = discord.utils.get(suggestion.reactions, emoji="✅")
        decline = discord.utils.get(suggestion.reactions, emoji="❌")
        close = discord.utils.get(suggestion.reactions, emoji="🔒")
        citation = (
            "\n> ".join(suggestion.content.split("\n"))
            + f"\n\n✅: {accept.count-1} vote(s), ❌: {decline.count-1} vote(s)"
        ) 
        accepted = str(payload.emoji) == accept.emoji
        declined = str(payload.emoji) == decline.emoji
        database.execute(
            update(SuggestionModel)
            .where(SuggestionModel.message_id == suggestion.id)
            .values(
                state="accepted" if accepted else "declined" if declined else "closed",
                date=datetime.now()
            )
        )
        if accepted:
            embed = discord.Embed(colour=0x77B255, title=f"Suggestion acceptée", description=f"> {citation}\n_**Note**: Il faut parfois attendre plusieurs jours avant qu'elle soit effective_")
        elif declined:
            embed = discord.Embed(colour=0xDD2E44, title=f"Suggestion refusée", description=f"> {citation}")
        else:
            embed = discord.Embed(colour=0xA9A6A7, title=f"Suggestion fermée", description=f"> {citation}")
        file = discord.File(STATIC_DIR / "img/alert.png")
        embed.set_thumbnail(url="attachment://alert.png")
        embed.set_author(name=suggestion.author.name)

        await channel.send(file=file, embed=embed)
        await suggestion.delete()

    @Cog.listener("on_message_delete")
    @has_any_role("Administrateur", "Modérateur")
    async def on_message_delete(self, message) -> None:
        """
        Delete suggestion in database when message is deleted.
        """
        database.execute(
            delete(SuggestionModel)
            .where(SuggestionModel.message_id == message.id)
        )

    @command(name="create_proposal")
    @has_any_role("Administrateur")
    async def create(self, ctx: discord.Interaction) -> None:
        """
        Send the proposal suggestion message
        """
        await self.__send_suggestions_rules(ctx.channel)
        await ctx.response.send_message("Le salon des suggestions a été créé.", ephemeral=True)

    @command(name="list")
    @choices(
        state=[
            Choice(name="En cours", value="open"),
            Choice(name="Acceptées", value="accepted"),
            Choice(name="Refusées", value="declined"),
            Choice(name="Fermées", value="closed"),
        ]
    )
    async def list(self, ctx, state: str) -> None:
        """
        Affiche les suggestions

        Parameters
        ----------
        state : str
            Le type de suggestions à afficher : En cours/Acceptées/Refusées/Fermées
        """
        suggestions = database.execute(
            select(SuggestionModel)
            .where(
                SuggestionModel.state == state,
                SuggestionModel.guild_id == ctx.guild.id
            )
            .order_by(SuggestionModel.date.desc())
            .limit(10)
        ).scalars().all()

        if not suggestions:
            await ctx.response.send_message("Aucune suggestion trouvée pour cet état.", ephemeral=True)
            return

        if state == "accepted":
            embed = discord.Embed(title=f"Suggestions acceptées", colour=0x77B255, timestamp=datetime.now())
        elif state == "declined":
            embed = discord.Embed(title=f"Suggestions refusées", colour=0xDD2E44, timestamp=datetime.now())
        elif state == "closed":
            embed = discord.Embed(title=f"Suggestions fermées", colour=0xA9A6A7, timestamp=datetime.now())
        else:
            embed = discord.Embed(title=f"Suggestions en cours", colour=0xA9A6A7, timestamp=datetime.now())

        for i, suggestion in enumerate(suggestions):

            embed.add_field(
                name=f"{i+1} - {suggestion.title} le {suggestion.date:%d/%m/%Y}",
                value=f"https://discord.com/channels/{ctx.guild.id}/{suggestion.channel_id}/{suggestion.message_id}",
                inline=False,
            )
        await ctx.response.send_message(embed=embed)

    class SuggestionsModal(Modal, title='Soumettre une suggestion'):
        def __init__(self, suggestion):
            super().__init__()
            self.suggestion = suggestion
            self.add_item(
                TextInput(
                    label='Titre de votre suggestion',
                    placeholder='Interdire pain au chocolat',
                    min_length=10,
                    max_length=80,
                    required=True
                )
            )
            self.add_item(
                TextInput(
                    label='Contenu de la suggestion',
                    placeholder=
                    "Le vocable chocolatine est à préférer quand le contexte le permet, c'est-à-dire dans tous les cas !",
                    min_length=30,
                    max_length=1024,
                    style=TextStyle.paragraph,
                    required=True
                )
            )

        async def on_submit(self, interaction: discord.Interaction):
            title = self.children[0].value
            content = self.children[1].value
            await interaction.response.send_message(f'Votre suggestion a été reçue et va être affichée.', ephemeral=True)
            await self.suggestion.make_suggestion(title, content, interaction.channel, interaction.user)

        async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
            await interaction.response.send_message("Quelque chose s'est mal passé lors de la réception !", ephemeral=True)

async def setup(bot) -> None:
    await bot.add_cog(Suggestion(bot))
