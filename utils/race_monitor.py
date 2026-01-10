# utils/race_monitor.py
import discord
import json
import os
from datetime import datetime, timedelta
import pytz
from utils.bungie_api import BungieAPI

PURPLE = 0x9B59B6

async def check_race_completions(bot, guild):
    """Check for new dungeon completions and update leaderboards"""
    
    events_file = f'./RaceEvents/{guild.id}.json'
    teams_file = f'./Teams/{guild.id}.json'
    
    if not os.path.exists(events_file) or not os.path.exists(teams_file):
        return
    
    with open(events_file, 'r') as f:
        events = json.load(f)
    
    with open(teams_file, 'r') as f:
        teams = json.load(f)
    
    now = datetime.now(pytz.UTC)
    bungie = BungieAPI(os.getenv('BUNGIE_API_KEY'))
    
    for race_id, race_data in events.items():
        start_date = datetime.fromisoformat(race_data['start_date'])
        end_date = datetime.fromisoformat(race_data['end_date'])
        
        # Skip if race hasn't started or has ended
        if now < start_date:
            continue
        
        if now > end_date:
            # Handle race end
            await handle_race_end(bot, guild, race_id, race_data, teams)
            continue
        
        # Race is active - check completions
        dungeon_hash = race_data['dungeon_hash']
        race_type = race_data['race_type']
        
        # Load or create results file
        results_file = f'./Results/{guild.id}/{race_id}_{end_date.strftime("%Y%m%d")}.json'
        os.makedirs(os.path.dirname(results_file), exist_ok=True)
        
        results = {}
        if os.path.exists(results_file):
            with open(results_file, 'r') as f:
                results = json.load(f)
        
        # Check each team's completions
        for team_name, team_data in teams.items():
            if team_data.get('race_id') != race_id:
                continue
            
            # Get captain's Bungie name (assuming it's stored)
            captain_name = team_data.get('captain')
            if not captain_name:
                continue
            
            # Fetch recent activities from Bungie API
            try:
                activities = await bungie.get_activity_history(
                    captain_name,
                    dungeon_hash,
                    start_date,
                    end_date
                )
                
                # Process activities
                valid_times = []
                for activity in activities:
                    # Validate: all team members present, no duplicates, fresh run
                    if validate_activity(activity, team_data['members']):
                        completion_time = activity['values']['activityDurationSeconds']['basic']['value']
                        valid_times.append(completion_time)
                
                # Sort times (best first)
                valid_times.sort()
                
                # Calculate result based on race type
                if race_type == 'best':
                    result_time = valid_times[0] if valid_times else None
                else:  # average
                    if len(valid_times) >= 3:
                        result_time = sum(valid_times[:3]) / 3
                    elif valid_times:
                        result_time = sum(valid_times) / len(valid_times)
                    else:
                        result_time = None
                
                # Store result
                results[team_name] = {
                    'time': result_time,
                    'completions': len(valid_times),
                    'all_times': valid_times[:10]  # Keep top 10
                }
                
            except Exception as e:
                print(f"Error checking completions for {team_name}: {e}")
                continue
        
        # Save results
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Update leaderboard
        await update_leaderboard(bot, guild, race_id, race_data, results)

def validate_activity(activity, team_members):
    """Validate that activity meets requirements"""
    # Check if it was a fresh run (no checkpoint)
    if activity.get('values', {}).get('startingPhaseIndex', {}).get('basic', {}).get('value', 0) != 0:
        return False
    
    # Get player names from activity
    players = []
    for entry in activity.get('entries', []):
        player_name = entry.get('player', {}).get('destinyUserInfo', {}).get('bungieGlobalDisplayName')
        if player_name:
            players.append(player_name)
    
    # Check all team members present
    for member in team_members:
        if member not in players:
            return False
    
    # Check no duplicate names
    if len(players) != len(set(players)):
        return False
    
    return True

async def update_leaderboard(bot, guild, race_id, race_data, results):
    """Update the leaderboard channel with current standings"""
    leaderboard_channel = discord.utils.get(guild.text_channels, name='leaderboard')
    if not leaderboard_channel:
        return
    
    # Sort teams by time
    sorted_teams = []
    for team_name, result in results.items():
        if result['time'] is not None:
            sorted_teams.append((team_name, result))
    
    # Sort: teams with times first (by time), then teams without times
    sorted_teams.sort(key=lambda x: x[1]['time'])
    
    # Teams without completions
    no_completion_teams = [name for name, res in results.items() if res['time'] is None]
    
    # Build leaderboard embed
    embed = discord.Embed(
        title=f"🏆 {race_id} - Leaderboard",
        description=f"**Dungeon:** {race_data['dungeon_name']}\n**Type:** {race_data['race_type'].capitalize()}",
        color=PURPLE
    )
    
    # Add ranked teams
    for i, (team_name, result) in enumerate(sorted_teams, 1):
        time_str = format_time(result['time'])
        
        if race_data['race_type'] == 'average':
            note = f" ({result['completions']}/3 runs)" if result['completions'] < 3 else ""
        else:
            note = ""
        
        embed.add_field(
            name=f"{i}. {team_name}",
            value=f"⏱️ {time_str}{note}",
            inline=False
        )
    
    # Add teams without completions
    if no_completion_teams:
        embed.add_field(
            name="No Completions Yet",
            value="\n".join([f"• {name}" for name in no_completion_teams]),
            inline=False
        )
    
    # Try to edit existing leaderboard message or create new one
    async for message in leaderboard_channel.history(limit=20):
        if message.author == bot.user and message.embeds:
            if message.embeds[0].title and race_id in message.embeds[0].title:
                await message.edit(embed=embed)
                return
    
    # Create new leaderboard message
    await leaderboard_channel.send(embed=embed)

async def handle_race_end(bot, guild, race_id, race_data, teams):
    """Handle race end procedures"""
    results_file = f'./Results/{guild.id}/{race_id}_{datetime.fromisoformat(race_data["end_date"]).strftime("%Y%m%d")}.json'
    
    if not os.path.exists(results_file):
        return
    
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    # Mark DNF for teams without enough completions
    for team_name, team_data in teams.items():
        if team_data.get('race_id') != race_id:
            continue
        
        if team_name not in results or results[team_name]['time'] is None:
            results[team_name] = {'time': None, 'completions': 0, 'status': 'DNF'}
        elif race_data['race_type'] == 'average' and results[team_name]['completions'] < 3:
            results[team_name]['status'] = 'DNF'
    
    # Save final results
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Post winners
    await post_winners(bot, guild, race_id, race_data, results)
    
    # Lock team channels
    for team_name, team_data in teams.items():
        if team_data.get('race_id') != race_id:
            continue
        
        text_channel = guild.get_channel(team_data.get('text_channel_id'))
        if text_channel:
            # Set read-only
            await text_channel.set_permissions(
                guild.default_role,
                read_messages=True,
                send_messages=False
            )
            
            # Post message
            await text_channel.send(
                f"**{race_id}** has ended. This channel has been locked and will be deleted in 2 days."
            )
            
            # Schedule deletion (you'd need to implement a task scheduler for this)
            # For now, just note it needs to be deleted

async def post_winners(bot, guild, race_id, race_data, results):
    """Post winning teams to winners-circle"""
    winners_channel = discord.utils.get(guild.text_channels, name='winners-circle')
    if not winners_channel:
        return
    
    # Get top 3 teams
    valid_results = [(name, res) for name, res in results.items() 
                     if res['time'] is not None and res.get('status') != 'DNF']
    valid_results.sort(key=lambda x: x[1]['time'])
    
    if not valid_results:
        return
    
    medals = ['🥇', '🥈', '🥉']
    
    embed = discord.Embed(
        title=f"🏆 {race_id} - Results",
        description=f"**Dungeon:** {race_data['dungeon_name']}",
        color=PURPLE
    )
    
    for i, (team_name, result) in enumerate(valid_results[:3]):
        medal = medals[i] if i < 3 else ''
        time_str = format_time(result['time'])
        
        # Get team members
        teams_file = f'./Teams/{guild.id}.json'
        with open(teams_file, 'r') as f:
            teams = json.load(f)
        
        members = teams.get(team_name, {}).get('members', [])
        members_str = "\n".join([f"• {m}" for m in members])
        
        embed.add_field(
            name=f"{medal} {i+1}. {team_name}",
            value=f"⏱️ {time_str}\n**Team:**\n{members_str}",
            inline=False
        )
    
    await winners_channel.send(embed=embed)

def format_time(seconds):
    """Format seconds into readable time string"""
    if seconds is None:
        return "No time"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"
