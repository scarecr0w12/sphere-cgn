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
            
            embed = discord.Embed(title=f"{server_info.get('servername', server)}", description=f"{server_info.get('description', 'N/A')}", color=discord.Color.blurple())
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
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"Error getting server info: {str(e)}", ephemeral=True)
            logging.error(f"Error getting server info: {str(e)}")

async def setup(bot):
    await bot.add_cog(ServerInfoCog(bot))
