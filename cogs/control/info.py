import discord
from discord.ext import commands
from discord import app_commands
from utils.database import server_autocomplete
from utils.apiutility import get_api_instance
import utils.constants as c
import logging

class ServerInfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def server_autocomplete(self, interaction: discord.Interaction, current: str):
        guild_id = interaction.guild.id
        server_names = await server_autocomplete(guild_id, current)
        choices = [app_commands.Choice(name=name, value=name) for name in server_names]
        return choices

    @app_commands.command(name="serverinfo", description="Get server info from the API.")
    @app_commands.describe(server="The name of the server to get info for.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.autocomplete(server=server_autocomplete)
    @app_commands.guild_only()
    async def server_info(self, interaction: discord.Interaction, server: str):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            api, error = await get_api_instance(interaction.guild.id, server)
            if error:
                await interaction.followup.send(error, ephemeral=True)
                return
            
            server_info = await api.get_server_info()
            server_metrics = await api.get_server_metrics()
            
            # Debug logging to see actual API response
            logging.info(f"Server info response type: {type(server_info)}, value: {server_info}")
            logging.info(f"Server metrics response type: {type(server_metrics)}, value: {server_metrics}")
            
            # Handle case where API might return None or empty dict
            if not server_info:
                server_info = {}
            if not server_metrics:
                server_metrics = {}
            
            # Try both snake_case and camelCase key names
            server_name = server_info.get('servername') or server_info.get('serverName') or server_info.get('name') or server
            description = server_info.get('description') or server_info.get('Description') or 'N/A'
            version = server_info.get('version') or server_info.get('Version') or 'N/A'
            world_guid = server_info.get('worldguid') or server_info.get('worldGuid') or server_info.get('WorldGUID') or 'N/A'
            
            current_players = server_metrics.get('currentplayernum') or server_metrics.get('currentPlayerNum') or server_metrics.get('currentPlayers') or 'N/A'
            max_players = server_metrics.get('maxplayernum') or server_metrics.get('maxPlayerNum') or server_metrics.get('maxPlayers') or 'N/A'
            days = server_metrics.get('days') or server_metrics.get('Days') or 'N/A'
            uptime = server_metrics.get('uptime') or server_metrics.get('Uptime')
            fps = server_metrics.get('serverfps') or server_metrics.get('serverFps') or server_metrics.get('fps') or server_metrics.get('FPS') or 'N/A'
            frametime = server_metrics.get('serverframetime') or server_metrics.get('serverFrameTime') or server_metrics.get('frametime') or server_metrics.get('FrameTime')
            
            embed = discord.Embed(title=f"{server_name}", description=f"{description}", color=discord.Color.blurple())
            embed.add_field(name="Players", value=f"{current_players}/{max_players}", inline=True)
            embed.add_field(name="Version", value=version, inline=True)
            embed.add_field(name="Days Passed", value=days, inline=True)
            
            # Handle uptime calculation safely
            uptime_str = f"{int(uptime / 60)} minutes" if uptime is not None and isinstance(uptime, (int, float)) else 'N/A'
            embed.add_field(name="Uptime", value=uptime_str, inline=True)
            
            embed.add_field(name="FPS", value=fps, inline=True)
            
            # Handle latency calculation safely
            latency_str = f"{frametime:.2f} ms" if frametime is not None and isinstance(frametime, (int, float)) else 'N/A'
            embed.add_field(name="Latency", value=latency_str, inline=True)
            
            embed.add_field(name="WorldGUID", value=f"`{world_guid}`", inline=False)
            embed.set_thumbnail(url=c.SPHERE_THUMBNAIL)
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"Error getting server info: {str(e)}", ephemeral=True)
            logging.error(f"Error getting server info: {str(e)}")

async def setup(bot):
    await bot.add_cog(ServerInfoCog(bot))
