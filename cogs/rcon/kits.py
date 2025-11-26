import json
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from utils.rconutility import RconUtility
from utils.database import (
    fetch_server_details,
    server_autocomplete,
    get_kit,
    save_kit,
    delete_kit,
    get_all_kit_names
)

async def autocomplete_kits(interaction: discord.Interaction, current: str):
    kit_names = await get_all_kit_names(current)
    return [app_commands.Choice(name=name, value=name) for name in kit_names]

class KitModal(discord.ui.Modal):
    def __init__(self, title, default_name="", default_commands="[]", default_desc=""):
        super().__init__(title=title)
        self.kit_name = discord.ui.TextInput(label="Kit Name", default=default_name)
        self.commands = discord.ui.TextInput(label="Commands (JSON)", style=discord.TextStyle.paragraph, default=default_commands)
        self.description = discord.ui.TextInput(label="Description", default=default_desc)
        self.add_item(self.kit_name)
        self.add_item(self.commands)
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        kit_name = self.kit_name.value.strip()
        commands_data = self.commands.value.strip()
        desc = self.description.value.strip()
        if not kit_name:
            await interaction.response.send_message("Kit name is required.", ephemeral=True)
            return
        try:
            json.loads(commands_data)
        except json.JSONDecodeError:
            await interaction.response.send_message("Commands must be valid JSON.", ephemeral=True)
            return
        await save_kit(kit_name, commands_data, desc)
        await interaction.response.send_message(f"Kit '{kit_name}' has been saved.", ephemeral=True)

class KitsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.rcon = RconUtility()

    async def get_server_info(self, guild_id: int, server_name: str):
        details = await fetch_server_details(guild_id, server_name)
        if details:
            return {"host": details[2], "password": details[3], "port": details[5]}

    async def autocomplete_server(self, interaction: discord.Interaction, current: str):
        guild_id = interaction.guild.id if interaction.guild else 0
        results = await server_autocomplete(guild_id, current)
        return [app_commands.Choice(name=x, value=x) for x in results[:25]]

    @app_commands.command(name="givekit", description="Give a kit to a user")
    @app_commands.describe(userid="User ID", kit_name="Kit Name", server="Server Name")
    @app_commands.autocomplete(server=autocomplete_server, kit_name=autocomplete_kits)
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def givekit(self, interaction: discord.Interaction, userid: str, kit_name: str, server: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send("No guild.", ephemeral=True)
            return
        server_info = await self.get_server_info(interaction.guild.id, server)
        if not server_info:
            await interaction.followup.send(f"Server not found: {server}", ephemeral=True)
            return
        kit = await get_kit(kit_name)
        if not kit:
            await interaction.followup.send(f"Kit not found: {kit_name}", ephemeral=True)
            return
        commands_str, desc = kit
        try:
            commands_list = json.loads(commands_str)
        except json.JSONDecodeError:
            await interaction.followup.send("Commands data is not valid JSON.", ephemeral=True)
            return
        for cmd_template in commands_list:
            final_cmd = cmd_template.format(userid=userid)
            await self.rcon.rcon_command(server_info["host"], server_info["port"], server_info["password"], final_cmd)
            await asyncio.sleep(1)
        await interaction.followup.send(f"Kit '{kit_name}' given to {userid} on '{server}'.", ephemeral=True)

    @app_commands.command(name="managekit", description="Create or update a kit.")
    @app_commands.describe(kit_name="Kit name (optional). If it exists, it will be loaded.")
    @app_commands.autocomplete(kit_name=autocomplete_kits)
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def manage_kit(self, interaction: discord.Interaction, kit_name: str = ""):
        if kit_name:
            existing = await get_kit(kit_name)
            if existing:
                commands_str, desc = existing
                modal = KitModal("Manage Kit", default_name=kit_name, default_commands=commands_str, default_desc=desc)
            else:
                modal = KitModal("Manage Kit")
        else:
            modal = KitModal("Manage Kit")
        await interaction.response.send_modal(modal)

    @app_commands.command(name="deletekit", description="Remove a kit from the database.")
    @app_commands.describe(kit_name="Kit name to remove")
    @app_commands.autocomplete(kit_name=autocomplete_kits)
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def deletekit(self, interaction: discord.Interaction, kit_name: str):
        await interaction.response.defer(ephemeral=True)
        await delete_kit(kit_name)
        await interaction.followup.send(f"Kit '{kit_name}' has been deleted.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(KitsCog(bot))
