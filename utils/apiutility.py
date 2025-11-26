from palworld_api import PalworldAPI
from utils.database import fetch_server_details

async def get_api_instance(guild_id: int, server_name: str):
    """
    Get a PalworldAPI instance for a given guild and server name.
    
    Args:
        guild_id: The Discord guild ID
        server_name: The name of the server
        
    Returns:
        tuple: (api_instance, error_message)
        - If successful: (PalworldAPI instance, None)
        - If failed: (None, error message string)
    """
    server_config = await fetch_server_details(guild_id, server_name)
    if not server_config:
        return None, f"Server '{server_name}' configuration not found."
    
    host = server_config[2]
    password = server_config[3]
    api_port = server_config[4]
    
    api = PalworldAPI(f"http://{host}:{api_port}", password)
    return api, None

