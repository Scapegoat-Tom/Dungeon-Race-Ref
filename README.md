# Destiny 2 Dungeon Race Bot

A Discord bot for organizing and tracking competitive Destiny 2 dungeon races with automatic time tracking via the Bungie API.

## Features

- 🏆 Create timed race events for any Destiny 2 dungeon
- 👥 Team management with private text and voice channels
- ⏱️ Automatic completion tracking via Bungie API
- 📊 Real-time leaderboards
- 🥇 Winners circle with medals
- 🎨 Purple-themed embeds

## Setup

### Prerequisites

- Python 3.10 or higher
- Discord Bot with proper permissions
- Bungie API Key
- Charlemagne Discord bot with "Warmind AutoNick" enabled [https://warmind.io](https://warmind.io/)

### Installation

1. **Clone or download the project**

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Create Discord Bot**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create new application
   - Go to Bot section and create a bot
   - Enable Privileged Gateway Intents:
     - ✅ Server Members Intent
     - ✅ Message Content Intent
   - Copy bot token

4. **Invite Bot to Server**
   - In OAuth2 > URL Generator select:
     - ✅ bot
     - ✅ applications.commands
   - Bot Permissions needed:
     - Manage Channels
     - Manage Events
     - Manage Roles
     - Read Messages/View Channels
     - Send Messages
     - Manage Messages
     - Embed Links
     - Read Message History
     - Connect (voice)
     - Move Members (voice)

5. **Get Bungie API Key**
   - Go to [Bungie Application Portal](https://www.bungie.net/en/Application)
   - Create new application
   - Set OAuth Client Type to "Not Applicable"
   - Copy API Key

6. **Configure Environment**
   - Copy `.env.example` to `.env`
   - Add your tokens:
```env
DISCORD_BOT_TOKEN=your_discord_bot_token_here
BUNGIE_API_KEY=your_bungie_api_key_here
```

7. **Run the bot**
```bash
python main.py
```

## Usage

### Initial Setup (Admin Only)

1. **Setup Race Channels**
```
/setup-dungeon-race
```
This creates:
- 📁 Dungeon Race (category)
  - 📜 dungeon-race-rules
  - 👥 teams
  - 📊 leaderboard
  - 🏆 winners-circle

### Creating a Race (Admin Only)

2. **Create Race Event**
```
/create-race-event
```
- Select dungeon from dropdown
- Fill in race details:
  - Race name (default: "Dungeon Race: [Dungeon]")
  - Start date/time (YYYY-MM-DD HH:MM AM/PM)
  - End date/time (YYYY-MM-DD HH:MM AM/PM)
  - Timezone (GMT, AST, EST, CST, PST)
  - Race type (average or best)

### Team Management (All Users)

3. **Create/Join Team**
```
/create-team
```
- Select active race
- Enter team name
- Add team members (Bungie names: Name#1234)
- Maximum 3 players per team

4. **Team Message Buttons**
- 🟢 **Join Team** - Join an existing team
- 🔴 **Leave Team** - Leave your current team
- 🔵 **Edit Name** - Change team name (captain only)
- ⚫ **Delete Team** - Delete team (captain only)

### During Race

- Bot automatically checks completions every hour
- Leaderboard updates automatically
- Only fresh runs count (no checkpoints)
- All team members must be present
- Each player can only appear once per run (no going to orbit or swapping character)

### After Race

- Final results posted to winners-circle
- Team channels locked (read-only)
- Channels deleted 2 days after race end
- Top 3 teams receive medals 🥇🥈🥉

## Admin Commands

| Command | Description |
|---------|-------------|
| `/setup-dungeon-race` | Create race category and channels |
| `/remove-dungeon-race` | Remove race category and channels |
| `/create-race-event` | Start a new race event |
| `/reset-teams` | Clear all teams before starting new race event (use with caution) |

## Race Types

### Best Time
- Your single fastest completion counts
- Perfect for speedrunners
- One perfect run wins

### Average Time
- Average of your three best runs
- Requires consistency
- More forgiving of mistakes
- Teams need at least 3 completions

## Validation Rules

The bot enforces these rules automatically:

✅ **Valid Runs**
- Fresh start (no checkpoint)
- All 3 team members present
- No duplicate players
- Within race time window

❌ **Invalid Runs**
- Started from checkpoint
- Missing team member(s)
- Player appears twice
- Outside race window

## File Structure

```
dungeon-race-bot/
├── main.py                 # Bot entry point
├── requirements.txt        # Python dependencies
├── .env                   # Configuration (create this)
│
├── cogs/                  # Command modules
│   ├── admin_commands.py  # Admin-only commands
│   ├── race_commands.py   # Race creation
│   └── team_commands.py   # Team management
│
├── utils/                 # Utility modules
│   ├── bungie_api.py      # Bungie API integration
│   ├── race_monitor.py    # Completion tracking
│   └── team_manager.py    # Team utilities
│
├── Resources/
│   └── dungeons.json      # Dungeon definitions
│
├── RaceEvents/            # Race data per server
│   └── [guild_id].json
│
├── Teams/                 # Team data per server
│   └── [guild_id].json
│
└── Results/               # Race results
    └── [guild_id]/
        └── [race_id]_[date].json
```

## Troubleshooting

### Bot doesn't respond to commands
- Check bot has proper permissions
- Verify bot is online
- Make sure intents are enabled

### Commands not showing up
- Wait a few minutes after starting bot
- Try kicking and re-inviting bot
- Check bot has `applications.commands` scope

### Bungie API not working
- Verify API key is correct
- Check player privacy settings
- Ensure Bungie names include code (#1234)

### Teams not tracking completions
- Verify Warmind AutoNick is enabled and server members are regstered with [https://warmind.io](https://warmind.io/). Bungie names must be the same as their server name, for example 'PlayerName#1234'.
- Check race has started
- Wait for hourly check (or restart bot)

## Customization

### Adding Dungeons

Edit `Resources/dungeons.json`:
```json
[
  {
    "name": "New Dungeon Name",
    "hash": 123456789
  }
]
```

Find activity hashes at [Destiny Sets](https://data.destinysets.com/)

### Changing Check Frequency

In `main.py`, modify the race monitor interval:
```python
@tasks.loop(hours=1)  # Change to minutes=30 for 30min checks
async def race_monitor():
```

### Theme Colors

Change `PURPLE = 0x9B59B6` in any file to your hex color.

## Support

For issues with:
- **Bot functionality**: Check this README
- **Bungie API**: Visit [Bungie API Documentation](https://bungie-net.github.io/multi/index.html)
- **Discord.py**: Visit [discord.py Documentation](https://discordpy.readthedocs.io/)

## License

This project is provided as-is for community use.

## Credits

- Built with [discord.py](https://github.com/Rapptz/discord.py)
- Powered by [Bungie.net API](https://bungie-net.github.io/)
- Created for the Destiny 2 community

---

Happy Racing, Guardian! 🏁
