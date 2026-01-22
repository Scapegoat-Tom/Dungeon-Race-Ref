# utils/race_monitor.py
import discord
import json
import os
from datetime import datetime
import pytz
import aiohttp

PURPLE = 0x9B59B6

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

async def check_race_completions(bot, guild):
    """Check for new dungeon completions and update leaderboards"""
    
    print(f"\n{'='*70}")
    print(f"🔍 RACE MONITOR CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Guild: {guild.name} (ID: {guild.id})")
    print(f"{'='*70}")
    
    events_file = f'./RaceEvents/{guild.id}.json'
    teams_file = f'./Teams/{guild.id}.json'
    
    # Check if files exist
    if not os.path.exists(events_file):
        print(f"⚠️  No race events file found: {events_file}")
        return
    
    if not os.path.exists(teams_file):
        print(f"⚠️  No teams file found: {teams_file}")
        return
    
    print(f"✓ Found race events file")
    print(f"✓ Found teams file")
    
    with open(events_file, 'r') as f:
        events = json.load(f)
    
    with open(teams_file, 'r') as f:
        teams = json.load(f)
    
    print(f"✓ Loaded {len(events)} race event(s)")
    print(f"✓ Loaded {len(teams)} team(s)")
    
    if not events:
        print("⚠️  No race events to check")
        return
    
    now = datetime.now(pytz.UTC)
    print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    bungie_api_key = os.getenv('BUNGIE_API_KEY')
    if not bungie_api_key:
        print("❌ BUNGIE_API_KEY not found in environment!")
        return
    
    print(f"✓ Initialized Bungie API")
    
    for race_id, race_data in events.items():
        print(f"\n{'-'*70}")
        print(f"📋 Checking race: {race_id}")
        
        start_date = datetime.fromisoformat(race_data['start_date'])
        end_date = datetime.fromisoformat(race_data['end_date'])
        
        print(f"   Start: {start_date.strftime('%Y-%m-%d %H:%M %Z')}")
        print(f"   End: {end_date.strftime('%Y-%m-%d %H:%M %Z')}")
        print(f"   Dungeon Hash: {race_data['dungeon_hash']}")
        print(f"   Race Type: {race_data['race_type']}")
        
        # Skip if race hasn't started
        if now < start_date:
            print(f"   ⏸️  Race hasn't started yet")
            continue
        
        # Check if race has ended
        if now > end_date:
            print(f"   🏁 Race has ended - handling race end")
            await handle_race_end(bot, guild, race_id, race_data, teams)
            continue
        
        print(f"   ✓ Race is ACTIVE")
        
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
            print(f"   ✓ Loaded existing results ({len(results)} teams)")
        else:
            print(f"   ✓ Creating new results file")
        
        # Count teams for this race
        race_teams = [t for t, d in teams.items() if d.get('race_id') == race_id]
        print(f"   ✓ Found {len(race_teams)} team(s) in this race")
        
        # Check each team's completions
        for team_name, team_data in teams.items():
            if team_data.get('race_id') != race_id:
                continue
            
            print(f"\n   🏃 Checking team: {team_name}")
            
            # Get team members
            team_members = team_data.get('members', [])
            if not team_members:
                print(f"      ⚠️  No team members found")
                continue
            
            print(f"      Team members: {', '.join(team_members)}")
            
            captain_name = team_members[0]
            print(f"      Captain: {captain_name}")
            
            # Fetch recent activities from Bungie API
            try:
                print(f"      🔍 Fetching activities from Bungie API...")
                completions = await get_completions(
                    bungie_api_key,
                    captain_name,
                    dungeon_hash,
                    start_date,
                    end_date
                )
                
                print(f"      ✓ Found {len(completions)} potential completion(s)")
                
                # Check if team composition has changed
                stored_team_members = results.get(team_name, {}).get('team_members', [])
                team_changed = sorted(team_members) != sorted(stored_team_members)
                
                if team_changed and stored_team_members:
                    print(f"      ⚠️  Team composition changed!")
                    print(f"         Old: {stored_team_members}")
                    print(f"         New: {team_members}")
                    print(f"      🔄 Re-validating all previous completions...")
                    
                    # Need to re-validate ALL previously processed instances
                    # Clear processed instances so they get re-checked
                    processed_instances = []
                else:
                    processed_instances = results.get(team_name, {}).get('processed_instances', [])
                
                print(f"      Already processed: {len(processed_instances)} completion(s)")
                
                # Process and validate activities
                valid_times = []
                
                new_completions = 0
                revalidated = 0
                invalidated = 0
                
                for completion in completions:
                    instance_id = completion['instance_id']
                    
                    # If team changed, re-validate everything
                    # Otherwise, skip already processed instances
                    if not team_changed and instance_id in processed_instances:
                        continue
                    
                    was_processed = instance_id in processed_instances
                    
                    print(f"      🔍 {'Re-validating' if was_processed else 'Validating new'} completion: {instance_id}")
                    
                    # Fetch PGCR and validate
                    pgcr = await get_pgcr(bungie_api_key, instance_id)
                    is_valid, reason = validate_completion(pgcr, team_members)
                    
                    if is_valid:
                        completion_time = completion['duration']
                        valid_times.append(completion_time)
                        processed_instances.append(instance_id)
                        if was_processed:
                            revalidated += 1
                            print(f"         ✓ STILL VALID - Time: {format_time(completion_time)}")
                        else:
                            new_completions += 1
                            print(f"         ✓ VALID - Time: {format_time(completion_time)}")
                    else:
                        if was_processed:
                            invalidated += 1
                            print(f"         ✗ NOW INVALID: {reason}")
                        else:
                            print(f"         ✗ Invalid: {reason}")
                
                if team_changed:
                    print(f"      Re-validation complete: {revalidated} still valid, {invalidated} invalidated")
                
                if new_completions > 0:
                    print(f"      ✓ Added {new_completions} new valid completion(s)")
                elif not team_changed:
                    print(f"      No new completions found")
                
                # All times are now in valid_times (only new/revalidated times from this check)
                # We need to combine with existing times ONLY if team hasn't changed
                if team_changed:
                    # Team changed - only use newly validated times
                    all_valid_times = valid_times
                else:
                    # Team unchanged - get existing valid times and add new ones
                    existing_times = results.get(team_name, {}).get('all_times', [])
                    # Combine existing and new times, remove duplicates by converting to set and back
                    all_valid_times = existing_times + valid_times
                
                all_valid_times.sort()  # Sort all times (best first)
                
                # Calculate result based on race type
                if race_type == 'best':
                    result_time = all_valid_times[0] if all_valid_times else None
                else:  # average
                    if len(all_valid_times) >= 3:
                        result_time = sum(all_valid_times[:3]) / 3
                    elif all_valid_times:
                        result_time = sum(all_valid_times) / len(all_valid_times)
                    else:
                        result_time = None
                
                # Store result with current team composition
                results[team_name] = {
                    'time': result_time,
                    'completions': len(all_valid_times),
                    'all_times': all_valid_times[:10],  # Keep top 10
                    'processed_instances': processed_instances,
                    'team_members': team_members  # Track team composition
                }
                
                if result_time:
                    print(f"      📊 Current result: {format_time(result_time)} ({len(all_valid_times)} completions)")
                else:
                    print(f"      📊 No valid completions yet")
                
            except Exception as e:
                print(f"      ❌ Error checking completions: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Save results
        try:
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n   💾 Results saved to: {results_file}")
        except Exception as e:
            print(f"\n   ❌ Error saving results: {e}")
        
        # Update leaderboard
        try:
            print(f"   📊 Updating leaderboard...")
            await update_leaderboard(bot, guild, race_id, race_data, results)
            print(f"   ✓ Leaderboard updated")
        except Exception as e:
            print(f"   ❌ Error updating leaderboard: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*70}")
    print(f"✅ Race monitor check complete")
    print(f"{'='*70}\n")

async def get_completions(api_key, bungie_name, dungeon_hash, start_date, end_date):
    """Get all completions for a player in a date range"""
    headers = {"X-API-Key": api_key}
    
    # Search for player
    if '#' not in bungie_name:
        return []
    
    name, code = bungie_name.split('#')
    
    url = "https://www.bungie.net/Platform/Destiny2/SearchDestinyPlayerByBungieName/-1/"
    payload = {
        "displayName": name,
        "displayNameCode": int(code)
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status != 200:
                return []
            
            data = await response.json()
            if not data.get('Response'):
                return []
            
            player = data['Response'][0]
            membership_type = player['membershipType']
            membership_id = player['membershipId']
    
    # Get characters
    url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/?components=200"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                return []
            
            data = await response.json()
            if 'Response' not in data or not data['Response']:
                return []
            
            characters_data = data.get('Response', {}).get('characters', {}).get('data', {})
            characters = list(characters_data.keys())
    
    all_completions = []
    
    # Check each character
    for char_id in characters:
        url = (
            f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Account/{membership_id}/"
            f"Character/{char_id}/Stats/Activities/?mode=82&count=50"
        )
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    continue
                
                data = await response.json()
                activities = data.get('Response', {}).get('activities', [])
                
                if not activities:
                    continue
                
                for activity in activities:
                    # Check if it's the right dungeon
                    ref_id = activity.get('activityDetails', {}).get('referenceId')
                    if ref_id != dungeon_hash:
                        continue
                    
                    # Check date range
                    period_str = activity.get('period')
                    activity_date = datetime.fromisoformat(period_str.replace('Z', '+00:00'))
                    
                    # Early exit if past start date
                    if activity_date < start_date:
                        break
                    
                    if not (start_date <= activity_date <= end_date):
                        continue
                    
                    # Check if completed
                    completed = activity.get('values', {}).get('completed', {}).get('basic', {}).get('value', 0)
                    if not completed or completed < 1:
                        continue
                    
                    # Get completion time
                    duration = activity.get('values', {}).get('activityDurationSeconds', {}).get('basic', {}).get('value', 0)
                    instance_id = activity.get('activityDetails', {}).get('instanceId')
                    
                    all_completions.append({
                        'instance_id': instance_id,
                        'date': activity_date,
                        'duration': duration
                    })
    
    return all_completions

async def get_pgcr(api_key, instance_id):
    """Get Post Game Carnage Report for an activity"""
    headers = {"X-API-Key": api_key}
    url = f"https://www.bungie.net/Platform/Destiny2/Stats/PostGameCarnageReport/{instance_id}/"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('Response')
    return None

def validate_completion(pgcr, team_members):
    """
    Validate that a completion meets race criteria:
    - EXACTLY the team members (no more, no less)
    - No duplicate players
    - Fresh run (no checkpoint)
    - All players present for full duration (no late joiners)
    """
    if not pgcr:
        return False, "No PGCR data"
    
    # Check if fresh run
    started_fresh = pgcr.get('activityWasStartedFromBeginning', False)
    if not started_fresh:
        return False, "Not a fresh run (checkpoint used)"
    
    # Get player names and their time played
    players_in_run = []
    player_times = {}
    activity_durations = []
    
    for entry in pgcr.get('entries', []):
        player_info = entry.get('player', {}).get('destinyUserInfo', {})
        player_name = f"{player_info.get('bungieGlobalDisplayName', '')}#{player_info.get('bungieGlobalDisplayNameCode', '')}"
        
        if player_name != '#':
            players_in_run.append(player_name)
            
            # Get time played
            time_played = entry.get('values', {}).get('timePlayedSeconds', {}).get('basic', {}).get('value', 0)
            player_times[player_name] = time_played
            
            # Get activity duration
            activity_duration = entry.get('values', {}).get('activityDurationSeconds', {}).get('basic', {}).get('value', 0)
            activity_durations.append(activity_duration)
    
    # CRITICAL: Check EXACT match - no extra players, no missing players
    if len(players_in_run) != len(team_members):
        return False, f"Player count mismatch: {len(players_in_run)} in run, {len(team_members)} on team"
    
    # Check all team members present
    missing_members = []
    for member in team_members:
        if member not in players_in_run:
            missing_members.append(member)
    
    if missing_members:
        return False, f"Missing team members: {', '.join(missing_members)}"
    
    # Check for extra players not on the team
    extra_players = []
    for player in players_in_run:
        if player not in team_members:
            extra_players.append(player)
    
    if extra_players:
        return False, f"Extra players not on team: {', '.join(extra_players)}"
    
    # Check that all players were present for full duration (+/- 30 seconds)
    total_duration = max(activity_durations) if activity_durations else 0
    for player, time_played in player_times.items():
        time_diff = abs(total_duration - time_played)
        if time_diff > 30:
            return False, f"{player} was not present for full run"
    
    # Check no duplicate players
    if len(players_in_run) != len(set(players_in_run)):
        return False, "Duplicate players in completion"
    
    return True, "Valid completion"

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
    print(f"   🏁 Handling race end for: {race_id}")
    
    results_file = f'./Results/{guild.id}/{race_id}_{datetime.fromisoformat(race_data["end_date"]).strftime("%Y%m%d")}.json'
    
    if not os.path.exists(results_file):
        print(f"   ⚠️  No results file found for ended race")
        # Remove race from events even if no results
        events_file = f'./RaceEvents/{guild.id}.json'
        with open(events_file, 'r') as f:
            events = json.load(f)
        if race_id in events:
            del events[race_id]
            with open(events_file, 'w') as f:
                json.dump(events, f, indent=2)
            print(f"   ✓ Removed race from events file")
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
    print(f"   ✓ Saved final results")
    
    # Post winners
    await post_winners(bot, guild, race_id, race_data, results)
    
    # Lock team channels
    for team_name, team_data in teams.items():
        if team_data.get('race_id') != race_id:
            continue
        
        text_channel = guild.get_channel(team_data.get('text_channel_id'))
        if text_channel:
            await text_channel.set_permissions(
                guild.default_role,
                read_messages=True,
                send_messages=False
            )
            
            await text_channel.send(
                f"**{race_id}** has ended. This channel has been locked and will be deleted in 2 days."
            )
    
    print(f"   ✓ Locked team channels")
    
    # Remove race from events file (race is complete)
    events_file = f'./RaceEvents/{guild.id}.json'
    with open(events_file, 'r') as f:
        events = json.load(f)
    
    if race_id in events:
        del events[race_id]
        with open(events_file, 'w') as f:
            json.dump(events, f, indent=2)
        print(f"   ✓ Removed race from events file")
    
    print(f"   🏁 Race end handling complete")

async def post_winners(bot, guild, race_id, race_data, results):
    """Post winning teams to winners-circle"""
    winners_channel = discord.utils.get(guild.text_channels, name='winners-circle')
    if not winners_channel:
        return
    
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
