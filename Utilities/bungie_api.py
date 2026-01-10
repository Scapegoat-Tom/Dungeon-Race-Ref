# utils/bungie_api.py
import aiohttp
import asyncio
from datetime import datetime

class BungieAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://www.bungie.net/Platform"
        self.headers = {
            "X-API-Key": api_key
        }
    
    async def search_player(self, bungie_name):
        """
        Search for a player by Bungie name (e.g., "PlayerName#1234")
        Returns membership info
        """
        # Split name and code
        if '#' not in bungie_name:
            raise ValueError("Bungie name must include code (e.g., PlayerName#1234)")
        
        name, code = bungie_name.split('#')
        
        url = f"{self.base_url}/Destiny2/SearchDestinyPlayerByBungieName/-1/"
        payload = {
            "displayName": name,
            "displayNameCode": code
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=payload) as response:
                if response.status != 200:
                    raise Exception(f"Failed to search player: {response.status}")
                
                data = await response.json()
                
                if not data.get('Response'):
                    raise Exception(f"Player not found: {bungie_name}")
                
                return data['Response'][0]  # Return first result
    
    async def get_activity_history(self, bungie_name, activity_hash, start_date, end_date, max_pages=5):
        """
        Get activity history for a player
        Filters by activity type (dungeon) and date range
        """
        # First, get player info
        player_info = await self.search_player(bungie_name)
        membership_type = player_info['membershipType']
        membership_id = player_info['membershipId']
        
        # Get character IDs
        characters = await self.get_characters(membership_type, membership_id)
        
        all_activities = []
        
        # Check each character
        for character_id in characters:
            page = 0
            while page < max_pages:
                url = (
                    f"{self.base_url}/Destiny2/{membership_type}/Account/{membership_id}/"
                    f"Character/{character_id}/Stats/Activities/"
                    f"?mode=82&page={page}&count=25"  # mode 82 is dungeons
                )
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=self.headers) as response:
                        if response.status != 200:
                            break
                        
                        data = await response.json()
                        activities = data.get('Response', {}).get('activities', [])
                        
                        if not activities:
                            break
                        
                        # Filter by activity hash and date
                        for activity in activities:
                            # Check if it's the right dungeon
                            if activity.get('activityDetails', {}).get('referenceId') != activity_hash:
                                continue
                            
                            # Check date range
                            activity_date = datetime.fromisoformat(
                                activity.get('period').replace('Z', '+00:00')
                            )
                            
                            if start_date <= activity_date <= end_date:
                                # Get full PGCR (Post Game Carnage Report)
                                pgcr = await self.get_pgcr(activity.get('activityDetails', {}).get('instanceId'))
                                if pgcr:
                                    all_activities.append(pgcr)
                        
                        page += 1
        
        return all_activities
    
    async def get_characters(self, membership_type, membership_id):
        """Get character IDs for a player"""
        url = f"{self.base_url}/Destiny2/{membership_type}/Profile/{membership_id}/?components=200"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    raise Exception(f"Failed to get characters: {response.status}")
                
                data = await response.json()
                characters_data = data.get('Response', {}).get('characters', {}).get('data', {})
                
                return list(characters_data.keys())
    
    async def get_pgcr(self, instance_id):
        """Get Post Game Carnage Report for an activity"""
        url = f"{self.base_url}/Destiny2/Stats/PostGameCarnageReport/{instance_id}/"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                return data.get('Response')
    
    async def validate_bungie_name(self, bungie_name):
        """Validate that a Bungie name exists"""
        try:
            await self.search_player(bungie_name)
            return True
        except:
            return False