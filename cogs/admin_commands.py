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
                    "**Rules:**\n"
                    "• All team members must be present in the completion\n"
                    "• Fresh runs only (no checkpoints)\n"
                    "• Each player can only be on one team per race\n"
                    "• No joining from orbit or character swapping\n"
                    "• No speed glitchs (skating), or off map travel\n"
                    "• No game exploits or other methods to bypass mechanics"
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
    @app_commands.command(name="cancel-race-event", description="Cancel an active race event")
    @app_commands.checks.has_permissions(administrator=True)
    async def cancel_race_event(self, interaction: discord.Interaction):
        events_file = f'./RaceEvents/{interaction.guild.id}.json'
        
        if not os.path.exists(events_file):
            await interaction.response.send_message("❌ No race events found!", ephemeral=True)
            return
        
        with open(events_file, 'r') as f:
            events = json.load(f)
        
        if not events:
            await interaction.response.send_message("❌ No race events to cancel!", ephemeral=True)
            return
        
        # Create dropdown for race selection
        options = [
            discord.SelectOption(label=race_id, value=race_id)
            for race_id in events.keys()
        ]
        
        select = discord.ui.Select(
            placeholder="Select a race to cancel",
            options=options,
            custom_id="cancel_race_select"
        )
        
        async def select_callback(select_interaction: discord.Interaction):
            selected_race = select_interaction.data['values'][0]
            
            await select_interaction.response.defer(ephemeral=True)
            
            # Load teams associated with this race
            teams_file = f'./Teams/{interaction.guild.id}.json'
            if os.path.exists(teams_file):
                with open(teams_file, 'r') as f:
                    teams = json.load(f)
                
                # Delete teams and their channels for this race
                teams_to_delete = []
                for team_name, team_data in teams.items():
                    if team_data.get('race_id') == selected_race:
                        teams_to_delete.append(team_name)
                        
                        # Delete team channels
                        if 'text_channel_id' in team_data:
                            text_channel = interaction.guild.get_channel(team_data['text_channel_id'])
                            if text_channel:
                                await text_channel.delete()
                        
                        if 'voice_channel_id' in team_data:
                            voice_channel = interaction.guild.get_channel(team_data['voice_channel_id'])
                            if voice_channel:
                                await voice_channel.delete()
                
                # Remove teams from file
                for team_name in teams_to_delete:
                    del teams[team_name]
                
                with open(teams_file, 'w') as f:
                    json.dump(teams, f, indent=2)
            
            # Delete Discord scheduled event
            for event in interaction.guild.scheduled_events:
                if event.name == selected_race:
                    try:
                        await event.delete()
                    except:
                        pass
            
            # Remove race from events file
            del events[selected_race]
            with open(events_file, 'w') as f:
                json.dump(events, f, indent=2)
            
            # Delete any leaderboard messages
            leaderboard_channel = discord.utils.get(interaction.guild.text_channels, name='leaderboard')
            if leaderboard_channel:
                async for message in leaderboard_channel.history(limit=50):
                    if message.author == self.bot.user and message.embeds:
                        if message.embeds[0].title and selected_race in message.embeds[0].title:
                            await message.delete()
            
            # Delete team messages
            teams_channel = discord.utils.get(interaction.guild.text_channels, name='teams')
            if teams_channel:
                async for message in teams_channel.history(limit=100):
                    if message.author == self.bot.user and message.embeds:
                        if message.embeds[0].description and selected_race in message.embeds[0].description:
                            await message.delete()
            
            embed = discord.Embed(
                title="🚫 Race Cancelled",
                description=f"**{selected_race}** has been cancelled.\n\nAll associated teams and channels have been removed.",
                color=PURPLE
            )
            await select_interaction.followup.send(embed=embed, ephemeral=True)
        
        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        
        await interaction.response.send_message("Select a race event to cancel:", view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
