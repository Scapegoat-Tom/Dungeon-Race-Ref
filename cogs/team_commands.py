# cogs/team_commands.py
import discord
from discord import app_commands
from discord.ext import commands
import json
import os

PURPLE = 0x9B59B6

class TeamCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="create-team", description="Create a team for a race")
    async def create_team(self, interaction: discord.Interaction):
        # Load race events
        events_file = f'./RaceEvents/{interaction.guild.id}.json'
        if not os.path.exists(events_file):
            await interaction.response.send_message(
                "❌ No active race events! An admin must create one first.",
                ephemeral=True
            )
            return
        
        with open(events_file, 'r') as f:
            events = json.load(f)
        
        if not events:
            await interaction.response.send_message(
                "❌ No active race events! An admin must create one first.",
                ephemeral=True
            )
            return
        
        # Create dropdown for race selection
        options = [
            discord.SelectOption(label=race_id, value=race_id)
            for race_id in events.keys()
        ]
        
        select = discord.ui.Select(
            placeholder="Select a race event",
            options=options,
            custom_id="race_select"
        )
        
        async def select_callback(select_interaction: discord.Interaction):
            selected_race = select_interaction.data['values'][0]
            modal = TeamModal(selected_race, select_interaction.user)
            await select_interaction.response.send_modal(modal)
        
        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        
        await interaction.response.send_message("Select a race to join:", view=view, ephemeral=True)

class TeamModal(discord.ui.Modal, title="Create Team"):
    def __init__(self, race_id, captain):
        super().__init__()
        self.race_id = race_id
        self.captain = captain
        
        self.team_name = discord.ui.TextInput(
            label="Team Name",
            placeholder="Enter your team name",
            max_length=50
        )
        
        self.member2 = discord.ui.TextInput(
            label="Team Member 2 (Optional)",
            placeholder="Bungie Name#1234",
            required=False,
            max_length=50
        )
        
        self.member3 = discord.ui.TextInput(
            label="Team Member 3 (Optional)",
            placeholder="Bungie Name#1234",
            required=False,
            max_length=50
        )
        
        self.add_item(self.team_name)
        self.add_item(self.member2)
        self.add_item(self.member3)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Load teams
        teams_file = f'./Teams/{interaction.guild.id}.json'
        teams = {}
        if os.path.exists(teams_file):
            with open(teams_file, 'r') as f:
                teams = json.load(f)
        
        # Collect all team members
        members = [self.captain.display_name]
        if self.member2.value:
            members.append(self.member2.value)
        if self.member3.value:
            members.append(self.member3.value)
        
        # Check for duplicate players across all teams
        for existing_team_name, existing_team_data in teams.items():
            if existing_team_data.get('race_id') != self.race_id:
                continue
            
            existing_members = existing_team_data.get('members', [])
            for member in members:
                if member in existing_members:
                    await interaction.response.send_message(
                        f"❌ Error: {member} is already on team '{existing_team_name}'. "
                        "Players can only be on one team per race. Try again!",
                        ephemeral=True
                    )
                    return
        
        # Check if team name already exists
        if self.team_name.value in teams:
            await interaction.response.send_message(
                f"❌ A team named '{self.team_name.value}' already exists!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Create team channels
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Dungeon Race")
        
        # Create text channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.captain: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        text_channel = await guild.create_text_channel(
            f"team-{self.team_name.value.lower().replace(' ', '-')}",
            category=category,
            overwrites=overwrites
        )
        
        # Create voice channel
        voice_channel = await guild.create_voice_channel(
            f"{self.team_name.value}",
            category=category,
            overwrites=overwrites
        )
        
        # Create team message in teams channel
        teams_channel = discord.utils.get(guild.text_channels, name='teams')
        
        embed = discord.Embed(
            title=f"🏁 {self.team_name.value}",
            description=(
                f"**Race:** {self.race_id}\n"
                f"**Captain:** {self.captain.mention}\n"
                f"**Members:**\n"
                + "\n".join([f"• {m}" for m in members])
            ),
            color=PURPLE
        )
        
        view = TeamView(self.team_name.value, interaction.guild.id)
        message = await teams_channel.send(embed=embed, view=view)
        
        # Save team data
        teams[self.team_name.value] = {
            'race_id': self.race_id,
            'captain': self.captain.display_name,
            'captain_id': self.captain.id,
            'members': members,
            'text_channel_id': text_channel.id,
            'voice_channel_id': voice_channel.id,
            'message_id': message.id
        }
        
        with open(teams_file, 'w') as f:
            json.dump(teams, f, indent=2)
        
        await interaction.followup.send(
            f"✅ Team '{self.team_name.value}' created! Check {text_channel.mention}",
            ephemeral=True
        )

class TeamView(discord.ui.View):
    def __init__(self, team_name, guild_id):
        super().__init__(timeout=None)
        self.team_name = team_name
        self.guild_id = guild_id
    
    @discord.ui.button(label="Join Team", style=discord.ButtonStyle.green, custom_id="join_team_btn")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.handle_join(interaction)
        except Exception as e:
            print(f"Error in join button: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="Leave Team", style=discord.ButtonStyle.red, custom_id="leave_team_btn")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.handle_leave(interaction)
        except Exception as e:
            print(f"Error in leave button: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="Edit Name", style=discord.ButtonStyle.blurple, custom_id="edit_team_btn")
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.handle_edit(interaction)
        except Exception as e:
            print(f"Error in edit button: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="Delete Team", style=discord.ButtonStyle.danger, custom_id="delete_team_btn")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.handle_delete(interaction)
        except Exception as e:
            print(f"Error in delete button: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
    
    async def handle_join(self, interaction: discord.Interaction):
        try:
            # DEFER IMMEDIATELY - interactions must be responded to within 3 seconds
            await interaction.response.defer(ephemeral=True)
            
            teams_file = f'./Teams/{interaction.guild.id}.json'
            
            if not os.path.exists(teams_file):
                await interaction.followup.send("❌ Teams file not found!", ephemeral=True)
                return
                
            with open(teams_file, 'r') as f:
                teams = json.load(f)
            
            team_data = teams.get(self.team_name)
            if not team_data:
                await interaction.followup.send("❌ Team not found!", ephemeral=True)
                return
            
            # Check if team is full
            if len(team_data['members']) >= 3:
                await interaction.followup.send("❌ Team is full (max 3 players)!", ephemeral=True)
                return
            
            # Check if user is already on this team
            user_name = interaction.user.display_name
            if user_name in team_data['members']:
                await interaction.followup.send("❌ You're already on this team!", ephemeral=True)
                return
            
            # Check if user is on another team for this race
            race_id = team_data['race_id']
            for other_team_name, other_team_data in teams.items():
                if other_team_data.get('race_id') == race_id and user_name in other_team_data.get('members', []):
                    await interaction.followup.send(
                        f"❌ You're already on team '{other_team_name}' for this race!",
                        ephemeral=True
                    )
                    return
            
            # Add user to team FIRST (before trying to set permissions)
            team_data['members'].append(user_name)
            
            # Update channel permissions (with better error handling)
            text_channel = interaction.guild.get_channel(team_data.get('text_channel_id'))
            voice_channel = interaction.guild.get_channel(team_data.get('voice_channel_id'))
            
            if text_channel:
                try:
                    await text_channel.set_permissions(
                        interaction.user, 
                        read_messages=True, 
                        send_messages=True,
                        view_channel=True
                    )
                    print(f"✓ Set text channel permissions for {interaction.user}")
                except discord.Forbidden as e:
                    print(f"✗ Failed to set text channel permissions: {e}")
                except Exception as e:
                    print(f"✗ Error setting text channel permissions: {e}")
            
            if voice_channel:
                try:
                    await voice_channel.set_permissions(
                        interaction.user, 
                        connect=True, 
                        speak=True,
                        view_channel=True
                    )
                    print(f"✓ Set voice channel permissions for {interaction.user}")
                except discord.Forbidden as e:
                    print(f"✗ Failed to set voice channel permissions: {e}")
                    # Don't fail the whole operation if voice permissions fail
                except Exception as e:
                    print(f"✗ Error setting voice channel permissions: {e}")
            
            # Save and update message
            teams[self.team_name] = team_data
            with open(teams_file, 'w') as f:
                json.dump(teams, f, indent=2)
            
            # Update embed
            captain = interaction.guild.get_member(team_data['captain_id'])
            embed = discord.Embed(
                title=f"🏁 {self.team_name}",
                description=(
                    f"**Race:** {team_data['race_id']}\n"
                    f"**Captain:** {captain.mention if captain else team_data['captain']}\n"
                    f"**Members:**\n"
                    + "\n".join([f"• {m}" for m in team_data['members']])
                ),
                color=PURPLE
            )
            
            await interaction.message.edit(embed=embed)
            await interaction.followup.send("✅ Joined team!", ephemeral=True)
            
        except Exception as e:
            print(f"Unexpected error in handle_join: {e}")
            import traceback
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
            else:
                try:
                    await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
                except:
                    pass
    
    async def handle_leave(self, interaction: discord.Interaction):
        try:
            # DEFER IMMEDIATELY
            await interaction.response.defer(ephemeral=True)
            
            teams_file = f'./Teams/{interaction.guild.id}.json'
            
            if not os.path.exists(teams_file):
                await interaction.followup.send("❌ Teams file not found!", ephemeral=True)
                return
                
            with open(teams_file, 'r') as f:
                teams = json.load(f)
            
            team_data = teams.get(self.team_name)
            if not team_data:
                await interaction.followup.send("❌ Team not found!", ephemeral=True)
                return
            
            user_name = interaction.user.display_name
            if user_name not in team_data['members']:
                await interaction.followup.send("❌ You're not on this team!", ephemeral=True)
                return
            
            # Remove user from team
            team_data['members'].remove(user_name)
            
            # Remove channel permissions
            text_channel = interaction.guild.get_channel(team_data.get('text_channel_id'))
            voice_channel = interaction.guild.get_channel(team_data.get('voice_channel_id'))
            
            if text_channel:
                try:
                    await text_channel.set_permissions(interaction.user, overwrite=None)
                except Exception as e:
                    print(f"✗ Error removing text channel permissions: {e}")
                    
            if voice_channel:
                try:
                    await voice_channel.set_permissions(interaction.user, overwrite=None)
                except Exception as e:
                    print(f"✗ Error removing voice channel permissions: {e}")
            
            # If captain left, promote next member or delete team
            if interaction.user.id == team_data['captain_id']:
                if len(team_data['members']) > 0:
                    # Find new captain
                    new_captain_name = team_data['members'][0]
                    new_captain = discord.utils.get(interaction.guild.members, display_name=new_captain_name)
                    if new_captain:
                        team_data['captain'] = new_captain.display_name
                        team_data['captain_id'] = new_captain.id
                else:
                    # Delete team if empty
                    try:
                        if text_channel:
                            await text_channel.delete()
                        if voice_channel:
                            await voice_channel.delete()
                        await interaction.message.delete()
                    except Exception as e:
                        print(f"✗ Error deleting channels: {e}")
                        
                    del teams[self.team_name]
                    with open(teams_file, 'w') as f:
                        json.dump(teams, f, indent=2)
                    await interaction.followup.send("✅ Left team! Team deleted (was empty).", ephemeral=True)
                    return
            
            # Save and update
            teams[self.team_name] = team_data
            with open(teams_file, 'w') as f:
                json.dump(teams, f, indent=2)
            
            # Update embed
            captain = interaction.guild.get_member(team_data['captain_id'])
            embed = discord.Embed(
                title=f"🏁 {self.team_name}",
                description=(
                    f"**Race:** {team_data['race_id']}\n"
                    f"**Captain:** {captain.mention if captain else team_data['captain']}\n"
                    f"**Members:**\n"
                    + "\n".join([f"• {m}" for m in team_data['members']])
                ),
                color=PURPLE
            )
            
            await interaction.message.edit(embed=embed)
            await interaction.followup.send("✅ Left team!", ephemeral=True)
            
        except Exception as e:
            print(f"Unexpected error in handle_leave: {e}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            except:
                pass
    
    async def handle_edit(self, interaction: discord.Interaction):
        teams_file = f'./Teams/{interaction.guild.id}.json'
        
        if not os.path.exists(teams_file):
            await interaction.response.send_message("❌ Teams file not found!", ephemeral=True)
            return
            
        with open(teams_file, 'r') as f:
            teams = json.load(f)
        
        team_data = teams.get(self.team_name)
        if not team_data:
            await interaction.response.send_message("❌ Team not found!", ephemeral=True)
            return
        
        # Only captain can edit
        if interaction.user.id != team_data['captain_id']:
            await interaction.response.send_message("❌ Only the team captain can edit the team name!", ephemeral=True)
            return
        
        modal = EditTeamModal(self.team_name, interaction.guild.id)
        await interaction.response.send_modal(modal)
    
    async def handle_delete(self, interaction: discord.Interaction):
        teams_file = f'./Teams/{interaction.guild.id}.json'
        
        if not os.path.exists(teams_file):
            await interaction.response.send_message("❌ Teams file not found!", ephemeral=True)
            return
            
        with open(teams_file, 'r') as f:
            teams = json.load(f)
        
        team_data = teams.get(self.team_name)
        if not team_data:
            await interaction.response.send_message("❌ Team not found!", ephemeral=True)
            return
        
        # Only captain can delete
        if interaction.user.id != team_data['captain_id']:
            await interaction.response.send_message("❌ Only the team captain can delete the team!", ephemeral=True)
            return
        
        # Delete channels
        text_channel = interaction.guild.get_channel(team_data['text_channel_id'])
        voice_channel = interaction.guild.get_channel(team_data['voice_channel_id'])
        
        if text_channel:
            await text_channel.delete()
        if voice_channel:
            await voice_channel.delete()
        
        # Delete team
        del teams[self.team_name]
        with open(teams_file, 'w') as f:
            json.dump(teams, f, indent=2)
        
        await interaction.message.delete()
        await interaction.response.send_message("✅ Team deleted!", ephemeral=True)

class EditTeamModal(discord.ui.Modal, title="Edit Team Name"):
    def __init__(self, old_team_name, guild_id):
        super().__init__()
        self.old_team_name = old_team_name
        self.guild_id = guild_id
        
        self.new_name = discord.ui.TextInput(
            label="New Team Name",
            placeholder="Enter new team name",
            default=old_team_name,
            max_length=50
        )
        self.add_item(self.new_name)
    
    async def on_submit(self, interaction: discord.Interaction):
        teams_file = f'./Teams/{self.guild_id}.json'
        with open(teams_file, 'r') as f:
            teams = json.load(f)
        
        # Check if new name already exists
        if self.new_name.value in teams and self.new_name.value != self.old_team_name:
            await interaction.response.send_message("❌ A team with that name already exists!", ephemeral=True)
            return
        
        # Update team name
        team_data = teams[self.old_team_name]
        del teams[self.old_team_name]
        teams[self.new_name.value] = team_data
        
        # Rename channels
        text_channel = interaction.guild.get_channel(team_data['text_channel_id'])
        voice_channel = interaction.guild.get_channel(team_data['voice_channel_id'])
        
        if text_channel:
            await text_channel.edit(name=f"team-{self.new_name.value.lower().replace(' ', '-')}")
        if voice_channel:
            await voice_channel.edit(name=self.new_name.value)
        
        with open(teams_file, 'w') as f:
            json.dump(teams, f, indent=2)
        
        # Update message
        captain = interaction.guild.get_member(team_data['captain_id'])
        embed = discord.Embed(
            title=f"🏁 {self.new_name.value}",
            description=(
                f"**Race:** {team_data['race_id']}\n"
                f"**Captain:** {captain.mention if captain else team_data['captain']}\n"
                f"**Members:**\n"
                + "\n".join([f"• {m}" for m in team_data['members']])
            ),
            color=PURPLE
        )
        
        view = TeamView(self.new_name.value, self.guild_id)
        await interaction.message.edit(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Team renamed to '{self.new_name.value}'!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(TeamCommands(bot))
