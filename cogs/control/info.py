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
            
            # Debug logging to see actual API response - use repr to see full structure
            logging.info(f"Server info response: {repr(server_info)}")
            logging.info(f"Server metrics response: {repr(server_metrics)}")
            
            # Handle case where API might return None or error response
            if server_info is None:
                await interaction.followup.send("Failed to retrieve server info from API. Please check your server configuration and ensure the REST API is enabled.", ephemeral=True)
                logging.error("API returned None for server_info")
                return
                
            if server_metrics is None:
                await interaction.followup.send("Failed to retrieve server metrics from API. Please check your server configuration and ensure the REST API is enabled.", ephemeral=True)
                logging.error("API returned None for server_metrics")
                return
            
            # Convert to dict if it's not already (might be a response object)
            if not isinstance(server_info, dict):
                # Try to get dict from response object
                if hasattr(server_info, '__dict__'):
                    server_info = server_info.__dict__
                elif hasattr(server_info, 'data'):
                    server_info = server_info.data
                elif hasattr(server_info, 'json'):
                    server_info = await server_info.json() if hasattr(server_info, 'json') else {}
                else:
                    logging.error(f"Server info is not a dict and can't be converted, it's {type(server_info)}: {repr(server_info)}")
                    await interaction.followup.send(f"Unexpected API response format. Check logs for details.", ephemeral=True)
                    return
                
            if not isinstance(server_metrics, dict):
                # Try to get dict from response object
                if hasattr(server_metrics, '__dict__'):
                    server_metrics = server_metrics.__dict__
                elif hasattr(server_metrics, 'data'):
                    server_metrics = server_metrics.data
                elif hasattr(server_metrics, 'json'):
                    server_metrics = await server_metrics.json() if hasattr(server_metrics, 'json') else {}
                else:
                    logging.error(f"Server metrics is not a dict and can't be converted, it's {type(server_metrics)}: {repr(server_metrics)}")
                    await interaction.followup.send(f"Unexpected API response format. Check logs for details.", ephemeral=True)
                    return
            
            # Log all available keys to help debug
            if isinstance(server_info, dict):
                logging.info(f"Server info keys: {list(server_info.keys())}")
                logging.info(f"Server info full content: {server_info}")
            if isinstance(server_metrics, dict):
                logging.info(f"Server metrics keys: {list(server_metrics.keys())}")
                logging.info(f"Server metrics full content: {server_metrics}")
            
            # If dicts are empty, show debug info to user
            if isinstance(server_info, dict) and isinstance(server_metrics, dict):
                if not server_info or not server_metrics:
                    info_keys = list(server_info.keys()) if server_info else "Empty"
                    metrics_keys = list(server_metrics.keys()) if server_metrics else "Empty"
                    debug_msg = (
                        f"**Debug Info:**\n"
                        f"Server Info Keys: {info_keys}\n"
                        f"Server Metrics Keys: {metrics_keys}\n"
                        f"Server Info: {server_info}\n"
                        f"Server Metrics: {server_metrics}"
                    )
                    # Truncate if too long
                    if len(debug_msg) > 2000:
                        debug_msg = debug_msg[:1900] + "... (truncated)"
                    await interaction.followup.send(f"```\n{debug_msg}\n```", ephemeral=True)
                    return
            
            # Try both snake_case and camelCase key names
            server_name = server_info.get('servername') or server_info.get('serverName') or server_info.get('name') or server_info.get('ServerName') or server
            description = server_info.get('description') or server_info.get('Description') or 'N/A'
            version = server_info.get('version') or server_info.get('Version') or 'N/A'
            world_guid = server_info.get('worldguid') or server_info.get('worldGuid') or server_info.get('WorldGUID') or server_info.get('worldGUID') or 'N/A'
            
            current_players = server_metrics.get('currentplayernum') or server_metrics.get('currentPlayerNum') or server_metrics.get('currentPlayers') or server_metrics.get('CurrentPlayerNum') or 'N/A'
            max_players = server_metrics.get('maxplayernum') or server_metrics.get('maxPlayerNum') or server_metrics.get('maxPlayers') or server_metrics.get('MaxPlayerNum') or 'N/A'
            days = server_metrics.get('days') or server_metrics.get('Days') or 'N/A'
            uptime = server_metrics.get('uptime') or server_metrics.get('Uptime')
            fps = server_metrics.get('serverfps') or server_metrics.get('serverFps') or server_metrics.get('fps') or server_metrics.get('FPS') or server_metrics.get('ServerFPS') or 'N/A'
            frametime = server_metrics.get('serverframetime') or server_metrics.get('serverFrameTime') or server_metrics.get('frametime') or server_metrics.get('FrameTime') or server_metrics.get('ServerFrameTime')
            
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
