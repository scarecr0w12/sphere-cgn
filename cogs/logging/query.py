import discord
from discord.ext import commands, tasks
from discord import app_commands
from utils.database import (
    server_autocomplete,
    fetch_server_details,
    add_query,
    fetch_query,
    delete_query,
    fetch_all_servers
)
from palworld_api import PalworldAPI
import utils.constants as c
import logging
import asyncio

class ServerQueryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_messages.start()

    def cog_unload(self):
        self.update_messages.cancel()

    @tasks.loop(seconds=180)
    async def update_messages(self):
        servers = await fetch_all_servers()
        for server in servers:
            guild_id, server_name, host, password, api_port, rcon_port = server
            message_ids = await fetch_query(guild_id, server_name)
            if message_ids:
                channel_id, message_id, player_message_id = message_ids
                channel = self.bot.get_channel(channel_id)
                if channel:
                    try:
                        server_config = await fetch_server_details(guild_id, server_name)
                        if not server_config:
                            continue

                        api = PalworldAPI(f"http://{host}:{api_port}", password)
                        server_info = await api.get_server_info()
                        server_metrics = await api.get_server_metrics()
                        player_list = await api.get_player_list()

                        # Skip if API returned errors
                        if isinstance(server_info, dict) and 'error' in server_info:
                            logging.warning(f"Skipping query update for {server_name}: API error - {server_info.get('error')}")
                            continue
                        if isinstance(server_metrics, dict) and 'error' in server_metrics:
                            logging.warning(f"Skipping query update for {server_name}: API error - {server_metrics.get('error')}")
                            continue

                        server_embed = self.create_server_embed(server_name, server_info, server_metrics)
                        player_embed = self.create_player_embed(player_list)

                        try:
                            message = await channel.fetch_message(message_id)
                            await message.edit(embed=server_embed)
                        except discord.NotFound:
                            message = await channel.send(embed=server_embed)
                            await add_query(guild_id, channel_id, server_name, message.id, player_message_id)
                        
                        await asyncio.sleep(5)

                        try:
                            player_message = await channel.fetch_message(player_message_id)
                            await player_message.edit(embed=player_embed)
                        except discord.NotFound:
                            player_message = await channel.send(embed=player_embed)
                            await add_query(guild_id, channel_id, server_name, message.id, player_message.id)

                        await asyncio.sleep(5)

                    except Exception as e:
                        logging.error(f"Error updating query server: '{server_name}': {str(e)}")

    def create_server_embed(self, server_name, server_info, server_metrics):
        # Handle error responses
        if isinstance(server_info, dict) and 'error' in server_info:
            embed = discord.Embed(
                title=f"{server_name} - Connection Error",
                description=f"Unable to connect to server API: {server_info.get('error')}",
                color=discord.Color.red()
            )
            return embed
            
        if isinstance(server_metrics, dict) and 'error' in server_metrics:
            embed = discord.Embed(
                title=f"{server_name} - Connection Error",
                description=f"Unable to connect to server API: {server_metrics.get('error')}",
                color=discord.Color.red()
            )
            return embed
        
        # Ensure we have dicts
        if not isinstance(server_info, dict):
            server_info = {}
        if not isinstance(server_metrics, dict):
            server_metrics = {}
            
        embed = discord.Embed(
            title=f"{server_info.get('servername', server_name)}",
            description=f"{server_info.get('description', 'N/A')}",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Players", value=f"{server_metrics.get('currentplayernum', 'N/A')}/{server_metrics.get('maxplayernum', 'N/A')}", inline=True)
        embed.add_field(name="Version", value=server_info.get('version', 'N/A'), inline=True)
        embed.add_field(name="Days Passed", value=server_metrics.get('days', 'N/A'), inline=True)
        
        # Handle uptime calculation safely
        uptime = server_metrics.get('uptime')
        uptime_str = f"{int(uptime / 60)} minutes" if uptime is not None and isinstance(uptime, (int, float)) else 'N/A'
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        
        embed.add_field(name="FPS", value=server_metrics.get('serverfps', 'N/A'), inline=True)
        
        # Handle latency calculation safely
        frametime = server_metrics.get('serverframetime')
        latency_str = f"{frametime:.2f} ms" if frametime is not None and isinstance(frametime, (int, float)) else 'N/A'
        embed.add_field(name="Latency", value=latency_str, inline=True)
        
        embed.add_field(name="WorldGUID", value=f"`{server_info.get('worldguid', 'N/A')}`", inline=False)
        embed.set_thumbnail(url=c.SPHERE_THUMBNAIL)
        return embed

    def create_player_embed(self, player_list):
        # Handle error responses
        if isinstance(player_list, dict) and 'error' in player_list:
            embed = discord.Embed(
                title="Players - Connection Error",
                description=f"Unable to retrieve player list: {player_list.get('error')}",
                color=discord.Color.red()
            )
            return embed
        
        # Ensure we have a dict with players
        if not isinstance(player_list, dict) or 'players' not in player_list:
            embed = discord.Embed(
                title="Players",
                description="Unable to retrieve player list (invalid response format)",
                color=discord.Color.orange()
            )
            return embed
        
        player_names = "\n".join([f"{player['name']}({player['accountName']}) - {player['userId']}" for player in player_list['players']])
        embed = discord.Embed(
            title="Players",
            color=discord.Color.green()
        )
        embed.add_field(name="Online Players", value=player_names if player_names else "No players online", inline=False)
        return embed
    
    async def server_names(self, interaction: discord.Interaction, current: str):
        guild_id = interaction.guild.id
        server_names = await server_autocomplete(guild_id, current)
        return [app_commands.Choice(name=name, value=name) for name in server_names]
    
    query_group = app_commands.Group(name="query", description="Query the server for information", default_permissions=discord.Permissions(administrator=True), guild_only=True)

    @query_group.command(name="add", description="Set the channel to query and log server info")
    @app_commands.describe(server="The name of the server", channel="The channel to log events in")
    @app_commands.autocomplete(server=server_names)
    async def add_query(self, interaction: discord.Interaction, server: str, channel: discord.TextChannel):
        try:
            await interaction.response.defer(ephemeral=True)
            guild_id = interaction.guild.id

            server_config = await fetch_server_details(guild_id, server)
            if not server_config:
                await interaction.followup.send(f"Server '{server}' configuration not found.", ephemeral=True)
                return

            host = server_config[2]
            password = server_config[3]
            api_port = server_config[4]

            api = PalworldAPI(f"http://{host}:{api_port}", password)
            server_info = await api.get_server_info()
            server_metrics = await api.get_server_metrics()
            player_list = await api.get_player_list()

            # Check for API errors
            if isinstance(server_info, dict) and 'error' in server_info:
                await interaction.followup.send(
                    f"**Connection Error:** {server_info.get('error')}\n\n"
                    f"Please verify your server configuration:\n"
                    f"• Server IP/Host: `{host}`\n"
                    f"• REST API Port: `{api_port}`\n"
                    f"• Admin Password is correct\n"
                    f"• REST API is enabled in server settings",
                    ephemeral=True
                )
                return
                
            if isinstance(server_metrics, dict) and 'error' in server_metrics:
                await interaction.followup.send(
                    f"**Connection Error:** {server_metrics.get('error')}\n\n"
                    f"Please verify your server configuration:\n"
                    f"• Server IP/Host: `{host}`\n"
                    f"• REST API Port: `{api_port}`\n"
                    f"• Admin Password is correct\n"
                    f"• REST API is enabled in server settings",
                    ephemeral=True
                )
                return

            server_embed = self.create_server_embed(server, server_info, server_metrics)
            player_embed = self.create_player_embed(player_list)

            message = await channel.send(embed=server_embed)
            player_message = await channel.send(embed=player_embed)

            await add_query(guild_id, channel.id, server, message.id, player_message.id)
            await interaction.followup.send(f"Query channel for server `{server}` set to {channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error in 'Add Query' command: {str(e)}", ephemeral=True)
            logging.error(f"Error in 'Add Query' command: {str(e)}")

    @query_group.command(name="remove", description="Remove the query channel for server info")
    @app_commands.describe(server="The name of the server")
    @app_commands.autocomplete(server=server_names)
    async def remove_query(self, interaction: discord.Interaction, server: str):
        try:
            await interaction.response.defer(ephemeral=True)
            guild_id = interaction.guild.id
            await delete_query(guild_id, server)
            await interaction.followup.send(f"Query channel for server `{server}` removed.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error in 'Remove Query' command: {str(e)}", ephemeral=True)
            logging.error(f"Error in 'Remove Query' command: {str(e)}")

async def setup(bot):
    await bot.add_cog(ServerQueryCog(bot))
