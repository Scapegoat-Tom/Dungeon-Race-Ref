# main.py
import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime
import asyncio
from pathlib import Path

# Create necessary directories
for directory in ['Resources', 'RaceEvents', 'Teams', 'Results']:
    Path(directory).mkdir(exist_ok=True)

# Initialize dungeons.json if it doesn't exist
dungeons_path = './Resources/dungeons.json'
if not os.path.exists(dungeons_path):
    default_dungeons = [
        {"name": "Grasp of Avarice", "hash": 4078656646},
        {"name": "Duality", "hash": 2823159265},
        {"name": "Spire of the Watcher", "hash": 1262462921},
        {"name": "Ghosts of the Deep", "hash": 4169648179},
        {"name": "Warlord's Ruin", "hash": 2136320021},
        {"name": "Vesper's Host", "hash": 442508465}
    ]
    with open(dungeons_path, 'w') as f:
        json.dump(default_dungeons, f, indent=2)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Purple theme color
PURPLE = 0x9B59B6

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    
    # Sync commands
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
    
    # Start monitoring task
    if not race_monitor.is_running():
        race_monitor.start()
    
    # Reinitialize team messages
    for guild in bot.guilds:
        await reinitialize_team_messages(guild)

@tasks.loop(hours=1)
async def race_monitor():
    """Monitor active races and update leaderboards"""
    from utils.race_monitor import check_race_completions
    
    for guild in bot.guilds:
        await check_race_completions(bot, guild)

@race_monitor.before_loop
async def before_race_monitor():
    await bot.wait_until_ready()

async def reinitialize_team_messages(guild):
    """Reinitialize team message buttons after bot restart"""
    from utils.team_manager import setup_team_message_view
    
    teams_file = f'./Teams/{guild.id}.json'
    if not os.path.exists(teams_file):
        return
    
    with open(teams_file, 'r') as f:
        teams_data = json.load(f)
    
    # Find teams channel
    teams_channel = discord.utils.get(guild.text_channels, name='teams')
    if not teams_channel:
        return
    
    # Recreate views for existing team messages
    for team_name, team_data in teams_data.items():
        if 'message_id' in team_data:
            try:
                message = await teams_channel.fetch_message(team_data['message_id'])
                view = setup_team_message_view(team_name, guild.id)
                await message.edit(view=view)
            except discord.NotFound:
                pass

# Load cogs (command modules)
async def load_cogs():
    cogs = [
        'cogs.admin_commands',
        'cogs.race_commands',
        'cogs.team_commands'
    ]
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f'Loaded {cog}')
        except Exception as e:
            print(f'Failed to load {cog}: {e}')

async def main():
    async with bot:
        await load_cogs()
        # Load your bot token from environment variable or config
        TOKEN = os.getenv('DISCORD_BOT_TOKEN')
        if not TOKEN:
            print("Error: DISCORD_BOT_TOKEN not found in environment variables")
            return
        await bot.start(TOKEN)

if __name__ == '__main__':
    asyncio.run(main())