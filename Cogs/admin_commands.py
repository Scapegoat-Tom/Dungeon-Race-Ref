# cogs/admin_commands.py
import discord
from discord import app_commands
from discord.ext import commands
import json
import os

PURPLE = 0x9B59B6

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup-dungeon-race", description="Setup dungeon race channels and category")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_dungeon_race(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        # Check if category already exists
        existing_category = discord.utils.get(guild.categories, name="Dungeon Race")
        if existing_category:
            await interaction.response.send_message("Dungeon Race category already exists!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Create category
        category = await guild.create_category("Dungeon Race")
        
        # Create channels
        channels_to_create = [
            ("dungeon-race-rules", "Rules and information for dungeon races"),
            ("teams", "View and manage race teams"),
            ("leaderboard", "Current race standings"),
            ("winners-circle", "Hall of fame for race winners")
        ]
        
        for channel_name, topic in channels_to_create:
            await guild.create_text_channel(channel_name, category=category, topic=topic)
        
        # Post initial message in rules channel
        rules_channel = discord.utils.get(category.text_channels, name="dungeon-race-rules")
        if rules_channel:
            embed = discord.Embed(
                title="🏆 Dungeon Race Rules",
                description=(
                    "Welcome to Dungeon Racing!\n\n"
                    "**How it works:**\n"
                    "1. Admins create race events with specific dungeons and timeframes\n"
                    "2. Create or join a team (max 3 players)\n"
                    "3. Complete the dungeon with your team during the race period\n"
                    "4. Your best time(s) are automatically tracked\n"
                    "5. Winners are announced when the race ends!\n\n"
                    "**Race Types:**\n"
                    "• **Best Time**: Your single fastest run counts\n"
                    "• **Average**: Average of your three best runs\n\n"
                    "**Important:**\n"
                    "• All team members must be present in the completion\n"
                    "• Fresh runs only (no checkpoints)\n"
                    "• Each player can only be on one team per race"
                ),
                color=PURPLE
            )
            await rules_channel.send(embed=embed)
        
        await interaction.followup.send("✅ Dungeon Race channels created successfully!", ephemeral=True)

    @app_commands.command(name="remove-dungeon-race", description="Remove dungeon race channels and category")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_dungeon_race(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Dungeon Race")
        
        if not category:
            await interaction.response.send_message("Dungeon Race category not found!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Delete all channels in the category
        for channel in category.channels:
            await channel.delete()
        
        # Delete the category
        await category.delete()
        
        await interaction.followup.send("✅ Dungeon Race category and channels removed!", ephemeral=True)

    @app_commands.command(name="reset-teams", description="Clear all teams for this server")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_teams(self, interaction: discord.Interaction):
        teams_file = f'./Teams/{interaction.guild.id}.json'
        
        if not os.path.exists(teams_file):
            await interaction.response.send_message("No teams to reset!", ephemeral=True)
            return
        
        # Load teams to delete their channels
        with open(teams_file, 'r') as f:
            teams_data = json.load(f)
        
        await interaction.response.defer(ephemeral=True)
        
        # Delete team channels
        for team_name, team_data in teams_data.items():
            if 'text_channel_id' in team_data:
                text_channel = interaction.guild.get_channel(team_data['text_channel_id'])
                if text_channel:
                    await text_channel.delete()
            
            if 'voice_channel_id' in team_data:
                voice_channel = interaction.guild.get_channel(team_data['voice_channel_id'])
                if voice_channel:
                    await voice_channel.delete()
        
        # Clear the teams file
        with open(teams_file, 'w') as f:
            json.dump({}, f, indent=2)
        
        # Clear team messages
        teams_channel = discord.utils.get(interaction.guild.text_channels, name='teams')
        if teams_channel:
            await teams_channel.purge(limit=100)
        
        await interaction.followup.send("✅ All teams have been reset!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))