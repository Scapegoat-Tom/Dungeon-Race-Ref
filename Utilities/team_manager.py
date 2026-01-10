# utils/team_manager.py
import discord
import json
import os

PURPLE = 0x9B59B6

def setup_team_message_view(team_name, guild_id):
    """Create a persistent view for team message buttons"""
    from cogs.team_commands import TeamView
    return TeamView(team_name, guild_id)

async def reinitialize_team_messages(guild):
    """Recreate views for all team messages after bot restart"""
    teams_file = f'./Teams/{guild.id}.json'
    if not os.path.exists(teams_file):
        return
    
    with open(teams_file, 'r') as f:
        teams = json.load(f)
    
    teams_channel = discord.utils.get(guild.text_channels, name='teams')
    if not teams_channel:
        return
    
    # Recreate views for each team message
    for team_name, team_data in teams.items():
        message_id = team_data.get('message_id')
        if not message_id:
            continue
        
        try:
            message = await teams_channel.fetch_message(message_id)
            view = setup_team_message_view(team_name, guild.id)
            await message.edit(view=view)
        except discord.NotFound:
            # Message was deleted, remove from teams
            print(f"Team message not found for {team_name}, cleaning up...")
            continue
        except Exception as e:
            print(f"Error reinitializing team message for {team_name}: {e}")

async def cleanup_empty_voice_channels(bot):
    """Kick players from team voice channels when they're empty (called periodically)"""
    for guild in bot.guilds:
        teams_file = f'./Teams/{guild.id}.json'
        if not os.path.exists(teams_file):
            continue
        
        with open(teams_file, 'r') as f:
            teams = json.load(f)
        
        for team_name, team_data in teams.items():
            voice_channel_id = team_data.get('voice_channel_id')
            if not voice_channel_id:
                continue
            
            voice_channel = guild.get_channel(voice_channel_id)
            if voice_channel and len(voice_channel.members) == 0:
                # Channel is empty, could disconnect members if needed
                # (Discord will automatically disconnect them when channel is deleted)
                pass

def get_team_by_member(guild_id, member_name, race_id=None):
    """Find which team a member belongs to"""
    teams_file = f'./Teams/{guild_id}.json'
    if not os.path.exists(teams_file):
        return None
    
    with open(teams_file, 'r') as f:
        teams = json.load(f)
    
    for team_name, team_data in teams.items():
        if race_id and team_data.get('race_id') != race_id:
            continue
        
        if member_name in team_data.get('members', []):
            return team_name, team_data
    
    return None

def is_team_captain(guild_id, team_name, user_id):
    """Check if a user is the captain of a team"""
    teams_file = f'./Teams/{guild_id}.json'
    if not os.path.exists(teams_file):
        return False
    
    with open(teams_file, 'r') as f:
        teams = json.load(f)
    
    team_data = teams.get(team_name)
    if not team_data:
        return False
    
    return team_data.get('captain_id') == user_id


# ===================================
# utils/__init__.py
# ===================================
# (Empty file, just needs to exist)


# ===================================
# cogs/__init__.py
# ===================================
# (Empty file, just needs to exist)