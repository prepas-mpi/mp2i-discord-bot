import logging
from datetime import datetime
from enum import Enum
from typing import Optional

import discord
from discord import TextStyle, Thread, Webhook
from discord.ext.commands import Cog, GroupCog, guild_only, hybrid_command
from discord.app_commands import Choice, choices
from discord.ui import Modal, TextInput
from sqlalchemy import delete, insert, select, update

from mp2i import STATIC_DIR
from mp2i.models import SuggestionModel
from mp2i.utils import database
from mp2i.wrappers.guild import GuildWrapper
from mp2i.utils.discord import has_any_role, defer

logger = logging.getLogger(__name__)

@guild_only()
class Suggestion(GroupCog, group_name="suggestions", description="Gestion des suggestions."):
    """
    Offers commands to allow members to propose suggestions and interact with them
    """

    def __init__(self, bot):
        self.bot = bot

    class State(Enum):
        """
        Enum for suggestion state
        """
        OPEN = "open"
        ACCEPTED = "accepted"
        DECLINED = "declined"
        CLOSED = "closed"

        @classmethod
        def from_str(cls, value: str):
            return cls(value)

    async def __send_suggestions_process(self, guild) -> None:
        """
        Display suggestions process.

        Parameters
        ----------
        channel : discord.TextChannel
            Channel where the suggestions process is sent
        """
        guild = GuildWrapper(guild)
        channel = guild.suggestion_channel
        if not channel:
            logger.warning("Guild %s has no suggestion channel", guild.id)
            return

        if guild.suggestion_message_id:
            try:
                message = await channel.fetch_message(guild.suggestion_message_id)
                await message.delete()
            except discord.NotFound:
                logger.warning("Suggestions message's id is set but no message was found maybe in another channel.")
        with open(STATIC_DIR / "text/suggestions.md", encoding="utf-8") as f:
            content = f.read()
        embed = discord.Embed(
            title="**Fonctionnement des suggestions**",
            description=content,
            colour=0xFF66FF,
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

    async def __make_suggestion(self, title, content, guild, user) -> None:
        """
        Create suggestion message, add reactions and then create a thread.

        Parameters
        ----------
        title : str
            Suggestion's title
        content : str
            Suggestion's content
        user : discord.User
            User who made the suggestion
        """
        guild = GuildWrapper(guild)
        if not guild:
            logger.warning("Guild %s not found", guild.id)
            return
        if not guild.suggestion_channel:
            logger.warning("Guild %s has no suggestion channel", guild.id)
            return
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
        msg = await guild.suggestion_channel.send(embed=embed)
        try:
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            thread = await guild.suggestion_channel.create_thread(
                name=title, message=msg
            )
            await thread.add_user(user)
        except discord.errors.NotFound:
            pass
        database.execute(
            insert(SuggestionModel).values(
                author_id=user.id,
                date=datetime.now(),
                guild_id=msg.guild.id,
                title=title,
                description=msg.content,
                message_id=msg.id,
                state=self.State.OPEN.value,
            )
        )
        await self.__send_suggestions_process(guild)

    async def __finish_suggestion(self, response: Webhook, thread: Thread, new_state: State, staff: int, reason: Optional[str]) -> None:
        """
        Close a suggestion

        Parameters
        ----------
        response : Webhook
            Response to the modal
        thread: Thread
            Suggestion's thread
        new_state : State
            Suggestion's new state
        staff: int
            Staff member who handled the suggestion
        reason : Optional[str]
            Close reason to display
        """
        suggestion = database.execute(
            select(SuggestionModel)
            .where(
                SuggestionModel.message_id == thread.id,
                SuggestionModel.state == self.State.OPEN.value
            )
            .order_by(SuggestionModel.date.desc())
            .limit(1)
        ).scalars().all()

        if not suggestion:
            await response.send(
                "Aucune suggestion trouvée. Êtes-vous dans le fil d'une suggestion ?", ephemeral=True
            )
            return

        suggestion = suggestion[0]
        if suggestion.state != self.State.OPEN.value:
            await response.send("La suggestion a déjà été traitée.", ephemeral=True)
            return

        message: Optional[discord.Message] = await thread.parent.fetch_message(suggestion.message_id)
        if not message:
            await response.send(
                "Aucun message correspondant à cette suggestion n'a pas été trouvée.", ephemeral=True
            )
            return
        content = f"<@{suggestion.author_id}>, votre suggestion a été "
        accept = discord.utils.get(message.reactions, emoji="✅").count - 1
        decline = discord.utils.get(message.reactions, emoji="❌").count - 1
        embed = message.embeds[0]
        embed.timestamp = datetime.now()
        if new_state == self.State.ACCEPTED:
            embed.colour = 0x1FC622
            embed.set_footer(text="✅ Suggestion acceptée")
            content += "acceptée."
        elif new_state == self.State.DECLINED:
            embed.colour = 0xFF6B60
            embed.set_footer(text="❌ Suggestion refusée")
            content += "refusée."
        elif new_state == self.State.CLOSED:
            embed.colour = 0xA2D2FF
            embed.set_footer(text="📦 Suggestion clôturée")
            content += "clôturée."
        embed.description = f"{embed.description}\n\n🗳 **Votes**\n{accept} ✅ • {decline} ❌"
        if reason:
            embed.description = f"{embed.description}\n\n\uD83D\uDCDD **Réponse de l'équipe**\n{reason}"
            content += " Vous retrouverez la raison de cette décision dans le message suivant :" + \
                f" {await self.__retrieve_message_url(thread.guild, suggestion)}."
        await thread.send(content)
        await message.edit(embed=embed)
        await message.clear_reactions()
        database.execute(
            update(SuggestionModel)
            .where(SuggestionModel.id == suggestion.id)
            .values(
                state=new_state.value,
                handled_by=staff,
                handled_time=datetime.now()
            )
        )
        await response.send("Suggestion traitée.", ephemeral=True)
        await thread.edit(locked=True, archived=True)


    @Cog.listener("on_interaction")
    async def send_suggestions_modal(self, interaction: discord.Interaction) -> None:
        """
        Send a modal to submit a suggestion.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction that triggered the event
        """
        if not ("custom_id" in interaction.data.keys()) or interaction.data["custom_id"] != "suggestion:proposal":
            return
        await interaction.response.send_modal(
            self.SuggestionsModal(
                lambda title, content: self.__make_suggestion(title, content, interaction.guild, interaction.user)
                )
        )

    @Cog.listener("on_message_delete")
    async def on_message_delete(self, message) -> None:
        """
        Delete suggestion in database when message is deleted.
        """
        database.execute(
            delete(SuggestionModel)
            .where(SuggestionModel.message_id == message.id)
        )

    @hybrid_command(name="create_proposal")
    @has_any_role("Administrateur")
    async def create(self, ctx) -> None:
        """
        Send the proposal suggestion message
        """
        guild = ctx.guild
        if not guild:
            await ctx.send("Vous devez être dans un serveur.", ephemeral=True)
            return

        guild = GuildWrapper(guild)
        if not guild.suggestion_channel:
            await ctx.send("Aucun salon de suggestions n'a été défini.", ephemeral=True)
            return

        await self.__send_suggestions_process(guild)
        await ctx.send("Le message de création de suggestions a été créé.", ephemeral=True)

    @hybrid_command(name="close")
    @has_any_role("Administrateur")
    @choices(
        state=[
            Choice(name="Accepter", value=State.ACCEPTED.value),
            Choice(name="Refuser", value=State.DECLINED.value),
            Choice(name="Fermer simplement", value=State.CLOSED.value),
        ]
    )
    async def close(self, ctx, state: str) -> None:
        """
        Send a modal to close a suggestion
        """
        if not isinstance(ctx.channel, Thread):
            await ctx.send("Vous devez être dans le fil d'une suggestion.", ephemeral=True)
            return
        thread: Thread = ctx.channel
        await ctx.interaction.response.send_modal(
            self.SuggestionsCloseModal(
            lambda interaction, reason: self.__finish_suggestion(
                interaction,
                thread,
                self.State.from_str(state),
                ctx.author.id,
                reason)
            )
        )

    async def __retrieve_message_url(self, guild, suggestion):
        """
        Get a jump URL to the suggestion message
        """
        guild = GuildWrapper(guild)
        if not guild:
            return None
        channel = guild.suggestion_channel
        if not channel:
            return None
        try:
            message = await channel.fetch_message(suggestion.message_id)
            return message.jump_url
        except discord.NotFound:
            logger.warning(f"Suggestion message not found for id {suggestion.id}.")
            return None


    @hybrid_command(name="list")
    @choices(
        state=[
            Choice(name="En cours", value=State.OPEN.value),
            Choice(name="Acceptées", value=State.ACCEPTED.value),
            Choice(name="Refusées", value=State.DECLINED.value),
            Choice(name="Fermées", value=State.CLOSED.value),
        ]
    )
    async def list(self, ctx, state: str) -> None:
        """
        Display suggestions list

        Parameters
        ----------
        state : str
            Suggestion's state to display (open, accepted, declined, closed)
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
        state = self.State.from_str(state)

        if not suggestions:
            await ctx.send("Aucune suggestion trouvée pour cet état.", ephemeral=True)
            return

        if state == self.State.ACCEPTED:
            embed = discord.Embed(title=f"Suggestions acceptées", colour=0x77B255, timestamp=datetime.now())
        elif state == self.State.DECLINED:
            embed = discord.Embed(title=f"Suggestions refusées", colour=0xDD2E44, timestamp=datetime.now())
        elif state == self.State.CLOSED:
            embed = discord.Embed(title=f"Suggestions fermées", colour=0xA9A6A7, timestamp=datetime.now())
        elif state == self.State.OPEN:
            embed = discord.Embed(title=f"Suggestions en cours", colour=0xA9A6A7, timestamp=datetime.now())
        else:
            await ctx.send("L'état demandé n'est pas supporté.", ephemeral=True)
            logger.error("État invalide pour la valeur %s", state)
            return

        for i, suggestion in enumerate(suggestions):

            embed.add_field(
                name=f"{i+1} - {suggestion.title} le {suggestion.date:%d/%m/%Y}",
                value=await self.__retrieve_message_url(ctx.guild, suggestion),
                inline=False,
            )
        await ctx.send(embed=embed)

    class SuggestionsModal(Modal, title='Soumettre une suggestion'):
        """
        Modal to submit a suggestion
        """

        def __init__(self, make_suggestion):
            super().__init__()
            self.make_suggestion = make_suggestion
            self.add_item(
                TextInput(
                    label='Titre de votre suggestion',
                    min_length=10,
                    max_length=80,
                    required=True
                )
            )
            self.add_item(
                TextInput(
                    label='Contenu de la suggestion',
                    placeholder=
                    "Veuillez être assez précis sur la description de votre suggestion," +
                    " elle ne pourra pas être modifiée.",
                    min_length=30,
                    max_length=3072,
                    style=TextStyle.paragraph,
                    required=True
                )
            )

        @defer(ephemeral=True)
        async def on_submit(self, interaction: discord.Interaction):
            title = self.children[0].value
            content = self.children[1].value
            await self.make_suggestion(title, content)
            await interaction.followup.send("Votre suggestion a bien été envoyée !", ephemeral=True)

        async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
            logger.error(error)
            await interaction.followup.send(
                "Une erreur interne est survenue, veuillez contacter un Administrateur.",
                ephemeral=True)

    class SuggestionsCloseModal(Modal, title="Fermer une suggestion"):
        """
        Modal to close a suggestion
        """

        def __init__(self, finish_suggestion):
            super().__init__()
            self.finish_suggestion = finish_suggestion
            self.add_item(
                TextInput(
                    label='Raison',
                    placeholder=
                    "Veuillez être assez précis sur la raison de la fermeture de la suggestion," +
                    " elle sera non modifiable.",
                    max_length=1000,
                    style=TextStyle.paragraph,
                    required=False
                )
            )

        @defer(ephemeral=True)
        async def on_submit(self, interaction: discord.Interaction):
            reason = self.children[0].value
            await self.finish_suggestion(interaction.followup, reason)

        async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
            logger.error(error)
            await interaction.followup.send(
                "Une erreur interne est survenue, veuillez contacter un Administrateur.",
                ephemeral=True)

async def setup(bot) -> None:
    await bot.add_cog(Suggestion(bot))
