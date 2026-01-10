# cogs/race_commands.py
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime
import pytz

PURPLE = 0x9B59B6

class RaceCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="create-race-event", description="Create a new dungeon race event")
    @app_commands.checks.has_permissions(administrator=True)
    async def create_race_event(self, interaction: discord.Interaction):
        # Load dungeons
        with open('./Resources/dungeons.json', 'r') as f:
            dungeons = json.load(f)
        
        # Create dropdown for dungeon selection
        options = [
            discord.SelectOption(label=dungeon['name'], value=str(dungeon['hash']))
            for dungeon in dungeons
        ]
        
        select = discord.ui.Select(
            placeholder="Select a dungeon",
            options=options,
            custom_id="dungeon_select"
        )
        
        async def select_callback(select_interaction: discord.Interaction):
            # Get selected dungeon
            selected_hash = int(select_interaction.data['values'][0])
            selected_dungeon = next(d for d in dungeons if d['hash'] == selected_hash)
            
            # Create modal for race details
            modal = RaceModal(selected_dungeon)
            await select_interaction.response.send_modal(modal)
        
        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        
        await interaction.response.send_message("Select a dungeon for the race:", view=view, ephemeral=True)

class RaceModal(discord.ui.Modal, title="Create Race Event"):
    def __init__(self, dungeon):
        super().__init__()
        self.dungeon = dungeon
        
        # Pre-fill race name
        default_name = f"Dungeon Race: {dungeon['name']}"
        
        self.race_name = discord.ui.TextInput(
            label="Race Name",
            placeholder="Dungeon Race: [Dungeon Name]",
            default=default_name,
            max_length=100
        )
        
        self.start_date = discord.ui.TextInput(
            label="Start Date and Time",
            placeholder="YYYY-MM-DD HH:MM AM/PM",
            max_length=50
        )
        
        self.end_date = discord.ui.TextInput(
            label="End Date and Time",
            placeholder="YYYY-MM-DD HH:MM AM/PM",
            max_length=50
        )
        
        self.timezone = discord.ui.TextInput(
            label="Time Zone",
            placeholder="GMT, AST, EST, CST, or PST",
            max_length=3
        )
        
        self.race_type = discord.ui.TextInput(
            label="Race Type",
            placeholder="average or best",
            max_length=10
        )
        
        self.add_item(self.race_name)
        self.add_item(self.start_date)
        self.add_item(self.end_date)
        self.add_item(self.timezone)
        self.add_item(self.race_type)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Validate timezone
        tz_map = {
            'GMT': 'GMT',
            'AST': 'America/Halifax',
            'EST': 'America/New_York',
            'CST': 'America/Chicago',
            'PST': 'America/Los_Angeles'
        }
        
        tz_input = self.timezone.value.upper()
        if tz_input not in tz_map:
            await interaction.response.send_message(
                "❌ Invalid timezone! Use: GMT, AST, EST, CST, or PST",
                ephemeral=True
            )
            return
        
        # Validate race type
        race_type = self.race_type.value.lower()
        if race_type not in ['average', 'best']:
            await interaction.response.send_message(
                "❌ Invalid race type! Use: 'average' or 'best'",
                ephemeral=True
            )
            return
        
        # Parse dates
        try:
            tz = pytz.timezone(tz_map[tz_input])
            start_dt = datetime.strptime(self.start_date.value, '%Y-%m-%d %I:%M %p')
            end_dt = datetime.strptime(self.end_date.value, '%Y-%m-%d %I:%M %p')
            
            # Make timezone aware
            start_dt = tz.localize(start_dt)
            end_dt = tz.localize(end_dt)
            
            # Validate dates
            if end_dt <= start_dt:
                await interaction.response.send_message(
                    "❌ End date must be after start date!",
                    ephemeral=True
                )
                return
            
        except ValueError as e:
            await interaction.response.send_message(
                f"❌ Invalid date format! Use: YYYY-MM-DD HH:MM AM/PM\nError: {str(e)}",
                ephemeral=True
            )
            return
        
        # Create race ID from race name
        race_id = self.race_name.value
        
        # Save race event
        events_file = f'./RaceEvents/{interaction.guild.id}.json'
        events = {}
        if os.path.exists(events_file):
            with open(events_file, 'r') as f:
                events = json.load(f)
        
        # Check if race already exists
        if race_id in events:
            await interaction.response.send_message(
                "❌ A race with this name already exists!",
                ephemeral=True
            )
            return
        
        events[race_id] = {
            'dungeon_name': self.dungeon['name'],
            'dungeon_hash': self.dungeon['hash'],
            'start_date': start_dt.isoformat(),
            'end_date': end_dt.isoformat(),
            'timezone': tz_input,
            'race_type': race_type
        }
        
        with open(events_file, 'w') as f:
            json.dump(events, f, indent=2)
        
        # Create Discord event
        rules_channel = discord.utils.get(interaction.guild.text_channels, name='dungeon-race-rules')
        description = (
            f"**Dungeon:** {self.dungeon['name']}\n"
            f"**Start:** {start_dt.strftime('%Y-%m-%d %I:%M %p')} {tz_input}\n"
            f"**End:** {end_dt.strftime('%Y-%m-%d %I:%M %p')} {tz_input}\n"
            f"**Type:** {race_type.capitalize()}\n"
            f"**Rules:** {rules_channel.mention if rules_channel else 'See #dungeon-race-rules'}"
        )
        
        try:
            event = await interaction.guild.create_scheduled_event(
                name=race_id,
                description=description,
                start_time=start_dt,
                end_time=end_dt,
                entity_type=discord.EntityType.external,
                location="Destiny 2",
                privacy_level=discord.PrivacyLevel.guild_only
            )
        except Exception as e:
            print(f"Failed to create Discord event: {e}")
        
        # Send confirmation
        embed = discord.Embed(
            title="✅ Race Event Created!",
            description=description,
            color=PURPLE
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(RaceCommands(bot))
