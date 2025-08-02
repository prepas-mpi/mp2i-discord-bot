from typing import Dict, List, Optional
from datetime import datetime

import discord
from discord.ext.commands import Cog, hybrid_command, guild_only

from mp2i import STATIC_DIR
from mp2i.utils.discord import has_any_role
from mp2i.wrappers.guild import GuildWrapper

class Tickets(Cog):

    def __init__(self, bot):
        self.bot = bot
        with open(f"{STATIC_DIR}/text/ticket.md", "r") as file:
            self.open_text = file.read()
        self.open_tickets: Dict[int, List[discord.Thread]] = {}
        self.is_setup = False

    @hybrid_command(name="create_ticket_message")
    @guild_only()
    @has_any_role("Administrateur")
    async def create_ticket_message(self, ctx):
        """
        Send an embed with a button to create new tickets

        Parameters
        ----------
        ctx: context of the slash command
        """
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.reply("Vous n'êtes pas dans un bon salon.", ephemeral=True)
            return
        
        channel: discord.TextChannel = ctx.channel

        embed: discord.Embed = discord.Embed(title="Système de tickets", description=self.open_text, colour=0xFF6B60)

        button: discord.ui.Button = discord.ui.Button(
            custom_id=f"ticket:open",
            style=discord.ButtonStyle.danger,
            label="Ouvrir un ticket",
            emoji="🎫"
        )
        view: discord.ui.View = discord.ui.View()
        view.add_item(button)

        await channel.send(embed=embed, view=view)

        await ctx.reply("Message envoyé.", ephemeral=True)

    @Cog.listener("on_interaction")
    async def open_ticket(self, interaction: discord.Interaction):
        """
        Create a new ticket

        Parameters
        ----------
        interaction: triggered by an interaction with a button
        """
        if not ("custom_id" in interaction.data.keys()) or interaction.data["custom_id"] != "ticket:open":
            return

        if not isinstance(interaction.channel, discord.TextChannel) or not interaction.guild:
            return

        # retrieve all open tickets
        if not self.is_setup:
            self.open_tickets[interaction.guild.id] = [
                thread for thread in interaction.channel.threads
                if thread.name.startswith("[Ouvert]") and
                not thread.locked and not thread.archived
            ]
            self.is_setup = True

        # check if a ticket is already open
        for thread in self.open_tickets[interaction.guild.id]:
            # last word of thread's name is user's name
            if thread.name.split(" ")[-1] == interaction.user.name:
                await interaction.response.send_message(
                    f"Vous avez déjà un ticket d'ouvert, accessible ici {thread.jump_url}. " +
                    "Merci de l'utiliser ou d'attendre que le précédent soit clôturé.",
                    ephemeral=True
                )
                return

        guild: GuildWrapper = GuildWrapper(interaction.guild)

        # create thread
        thread: discord.Thread = await interaction.channel.create_thread(
            name=f"[Ouvert] Ticket de {interaction.user.name}",
            invitable=False
        )
        self.open_tickets[interaction.guild.id].append(thread)

        # a message is sent after the creation to block button's interaction
        await interaction.response.send_message("Création d'un thread...", ephemeral=True)

        # add staff by ping in an edited message
        
        await interaction.edit_original_response(content="Ajout du staff...")
        
        role_list: List[Optional[discord.Role]] = [guild.get_role_by_qualifier("Administrateur"),
                                        guild.get_role_by_qualifier("Modérateur")]
        mentions: str = " ".join([role.mention for role in role_list if role])

        message: discord.Message = await thread.send("(╯°□°)╯︵ ┻━┻")
        await message.edit(content=mentions)
        await message.delete()

        # create a small embed to have a reason to send a button to close ticket
        
        await interaction.edit_original_response(content="Ajout d'un message initial...")

        embed: discord.Embed = discord.Embed(
            title="Ticket",
            description=f"{interaction.user.mention}, vous pouvez dès à présent expliquer la raison de l'ouverture de ce ticket.",
            timestamp=datetime.now()
        )

        button: discord.ui.Button = discord.ui.Button(
            custom_id="ticket:close",
            style=discord.ButtonStyle.secondary,
            label="Clôturer le ticket",
            emoji="🔏"
        )

        view: discord.ui.View = discord.ui.View()
        view.add_item(button)

        await thread.send(embed=embed, view=view)

        # add claimant
        
        await interaction.edit_original_response(content="Ajout du demandeur...")

        message = await thread.send(f"{interaction.user.mention}")
        await message.delete()
        
        await interaction.edit_original_response(content=f"Votre ticket est accessible dans le salon {thread.jump_url}")

    @Cog.listener("on_interaction")
    async def close_ticket(self, interaction: discord.Interaction):
        """
        Close an opened ticket

        Parameters
        ----------
        interaction: triggered by an interaction with a button
        """
        if not ("custom_id" in interaction.data.keys()) or interaction.data["custom_id"] != "ticket:close":
            return

        if not isinstance(interaction.channel, discord.Thread) or not interaction.guild:
            return

        # check user's permission
        
        guild: GuildWrapper = GuildWrapper(interaction.guild)

        admin_role: Optional[discord.Role] = guild.get_role_by_qualifier("Administrateur")
        mod_role: Optional[discord.Role] = guild.get_role_by_qualifier("Modérateur")

        if not admin_role or not mod_role:
            return

        member: Optional[discord.Member] = guild.get_member(interaction.user.id)
        
        if not member or not member.get_role(admin_role.id) and not member.get_role(mod_role.id):
            await interaction.response.send_message("Vous ne pouvez pas fermer le ticket.", ephemeral=True)
            return

        # lock and archive thread
        
        thread: discord.Thread = interaction.channel

        await thread.send("Le ticket va maintenant être archivé.")

        await interaction.response.send_message("Archivage du thread...", ephemeral=True)

        # change thread's name's prefix
        
        name: str = f"[Fermé] {' '.join(thread.name.split(' ')[1:])}"
        
        await thread.edit(name=name, locked=True, archived=True)

        # remove from cache if it has been setup
        if self.is_setup:
            self.open_tickets[interaction.guild.id] = [
                cache for cache in self.open_tickets[interaction.guild.id]
                if cache.id != thread.id
            ]

        await interaction.edit_original_response(content="Thread archivé")
        
async def setup(bot) -> None:
    await bot.add_cog(Tickets(bot))
