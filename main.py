import asyncio
import json
import discord
from discord.ext import commands
from discord import ui
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
# Guild ID is the server where the bot operates
# Might need to be changed to support multiple guilds
GUILD_ID = int(os.getenv("GUILD_ID"))
# Channel name for the office tracker dashboard
OFFICE_TRACKER_CHANNEL_NAME = os.getenv(
    "OFFICE_TRACKER_CHANNEL_NAME", "office-tracker"
)
RFID_ENABLED = os.getenv("RFID_ENABLED", "False").lower() == "true"

# We need the members intent to get user info
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(intents=intents)

# TODO: Persist data in a database or file for long-term storage. Maybe add logging.
# In-memory list to track who is in the office, mapping user display names to entry times
office_attendees: dict[str, datetime] = {}

# TODO: could look into non-members being on the attendees list
# Mapping of Discord IDs to user info
# Load members mapping from members.json (keys are Discord IDs)
members_file = os.path.join(os.path.dirname(__file__), "members.json")
members: dict[int, dict[str, str]] = {}

try:
    with open(members_file, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # Convert string keys to int if necessary
    for k, v in raw.items():
        try:
            discord_id = int(k)
        except Exception:
            continue
        if isinstance(v, dict):
            members[discord_id] = {"name": v.get("name"), "uid": v.get("uid")}
except FileNotFoundError:
    # Create a sample file if it doesn't exist
    sample = {
        "1437268694182002721": {"name": "BOT - The Office Bot", "uid": "CA421100"},
    }
    with open(members_file, "w", encoding="utf-8") as f:
        json.dump(sample, f, indent=2)
    members = {int(k): v for k, v in sample.items()}
except Exception as e:
    print(f"Failed to load members from {members_file}: {e}")
    members = {}

print("RFID functionality is", "enabled" if RFID_ENABLED else "disabled")
print(f"Loaded {len(members)} members from {members_file}")
print("Members:")
for member in members.values():
    print(f" - {member['name']}")


def discord_id_from_uid(uid: str):
    """
    Get the Discord ID associated with a given RFID UID.
    """
    for discord_id, info in members.items():
        if info["uid"] == uid:
            return discord_id
    return None


# -----------------------------
# Button View
# -----------------------------
class OfficeButtons(ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # persistent

    # User entry button
    @ui.button(
        label="Entering 🟩", style=discord.ButtonStyle.green, custom_id="enter_button"
    )
    async def enter(self, button: ui.Button, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id not in members:
            await self.update_embed(
                interaction, f"Unknown user {user_id} tried to enter the office."
            )
            return

        name = members[user_id]["name"]
        if name in office_attendees:
            await self.update_embed(interaction, f"{name} is already in the office!")
            return
        office_attendees[name] = datetime.now()
        await self.update_embed(interaction, f"{name} entered the office!")

    # User exit button
    @ui.button(
        label="Leaving 🟥", style=discord.ButtonStyle.red, custom_id="leave_button"
    )
    async def leave(self, button: ui.Button, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id not in members:
            await self.update_embed(
                interaction, f"Unknown user {user_id} tried to leave the office."
            )
            return

        name = members[user_id]["name"]
        if name not in office_attendees:
            await self.update_embed(interaction, f"{name} is not in the office!")
            return
        office_attendees.pop(name)
        await self.update_embed(interaction, f"{name} left the office!")

    # Refresh button
    @ui.button(
        label="Refresh 🔄", style=discord.ButtonStyle.gray, custom_id="refresh_button"
    )
    async def refresh_button(self, button: ui.Button, interaction: discord.Interaction):
        await self.update_embed(interaction, "Refreshed!")

    # Clear all button
    @ui.button(
        label="Clear All 🧹",
        style=discord.ButtonStyle.blurple,
        custom_id="clear_button",
    )
    async def clear_all(self, button: ui.Button, interaction: discord.Interaction):
        office_attendees.clear()
        await self.update_embed(interaction, "Cleared all office members!")

    # Embed updater. It edits the original message if possible, otherwise sends a new one.
    async def update_embed(self, interaction: discord.Interaction, message: str):
        # Refresh the dashboard for the guild where the interaction happened
        # NOTE: could make it refresh from a list of known guilds if needed
        guild = interaction.guild

        if guild is not None:
            await refresh_dashboard(guild, message)
        else:
            print("Could not determine guild to refresh dashboard.")
            # Acknowledge the interaction to avoid "This interaction failed" errors.
        
        await interaction.response.defer()

# -----------------------------
# Helper Functions
# -----------------------------
async def refresh_dashboard(guild: discord.Guild, message: str = None):
    """
    Refresh the office presence dashboard for the given guild. Edits the existing message in specified channel.
    """
    # Find the dashboard message by locating the view
    print(f"Refreshing dashboard for guild: {guild.name} ({guild.id})")
    if message:
        print(message)
    for channel in guild.text_channels:
        if channel.name != OFFICE_TRACKER_CHANNEL_NAME:
            continue
        async for msg in channel.history(limit=50):
            if msg.author == guild.me and msg.components:
                # Rebuild the embed
                if len(office_attendees) == 0:
                    value = "No one is currently in the office."
                else:
                    value = "\n".join(
                        [
                            f"• {name} (since {time.strftime('%H:%M')})"
                            for name, time in office_attendees.items()
                        ]
                    )

                embed = discord.Embed(
                    title="🏢 IEEE Office Presence",
                    description="Use the buttons below to check in or out.",
                    color=0x2ECC71,
                )
                embed.add_field(name="Currently in office:", value=value, inline=False)
                embed.set_footer(
                    text=f"Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )

                await msg.edit(embed=embed)


# -----------------------------
# Slash Command
# -----------------------------
@bot.slash_command(
    name="setup", description="[Admin] Create the office presence dashboard"
)
@commands.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    """
    Set up the office presence dashboard.
    Creates an embed with buttons. It will be persisted and updated.
    """
    embed = discord.Embed(
        title="🏢 IEEE Office Presence",
        description="Use the buttons below to check in or out.",
        color=0x2ECC71,
    )
    embed.add_field(name="Currently in office:", value="No one yet!", inline=False)

    view = OfficeButtons()
    await interaction.response.send_message(embed=embed, view=view)


@bot.slash_command(name="add", description="Add a user to the office manually")
async def add(interaction: discord.Interaction, member: discord.Member):
    """
    Add a user to the office manually."""
    user_id = member.id
    if user_id not in members:
        await interaction.response.send_message(
            f"User {member.display_name} is not recognized!", ephemeral=True
        )
        return

    name = members[user_id]["name"]
    if name in office_attendees:
        await interaction.response.send_message(
            f"{name} is already in the office!", ephemeral=True
        )
        return

    office_attendees[name] = datetime.now()
    await interaction.response.send_message(
        f"Added {name} to the office manually!", ephemeral=True
    )

    # Update the embed if possible
    await refresh_dashboard(interaction.guild)


@bot.slash_command(name="remove", description="Remove a user from the office manually")
async def remove(interaction: discord.Interaction, member: discord.Member):
    """
    Remove a user from the office manually.
    """
    user_id = member.id
    if user_id not in members:
        await interaction.response.send_message(
            f"User {member.display_name} is not recognized!", ephemeral=True
        )
        return

    name = members[user_id]["name"]
    if name not in office_attendees:
        await interaction.response.send_message(
            f"{name} is not in the office!", ephemeral=True
        )
        return

    office_attendees.pop(name)
    await interaction.response.send_message(
        f"Removed {name} from the office manually!", ephemeral=True
    )

    # Update the embed if possible
    await refresh_dashboard(interaction.guild)


@bot.slash_command(
    name="memberids",
    description="List all members and their IDs in the channel",
)
async def list_members(interaction: discord.Interaction):
    """
    List all members and their IDs.
    """
    channel = interaction.channel
    if channel is None:
        await interaction.response.send_message(
            "Could not determine the channel.", ephemeral=True
        )
        return

    members = channel.members  # members who can see the channel
    if not members:
        await interaction.response.send_message(
            "No members visible in this channel.", ephemeral=True
        )
        return

    member_list = "\n".join(
        [
            f"{m.display_name} — {m.id}"
            for m in sorted(members, key=lambda m: m.display_name.lower())
        ]
    )

    print(member_list)
    await interaction.response.send_message(
        f"Members in this channel:\n{member_list}", ephemeral=True
    )


@bot.slash_command(name="guildid", description="Show the Guild ID")
async def show_guild_id(interaction: discord.Interaction):
    """
    Show the Guild ID.
    """
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "Could not determine the guild.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"The Guild ID is: {guild.id}", ephemeral=True
    )


@bot.slash_command(name="members", description="Show all registered members")
async def show_members(interaction: discord.Interaction):
    """
    Show all registered members.
    """
    if not members:
        await interaction.response.send_message(
            "No members are registered.", ephemeral=True
        )
        return

    member_list = "\n".join(
        [f"{info['name']} — UID: {info.get('uid') or '(not registered)'}" for info in members.values()]
    )

    await interaction.response.send_message(
        f"Registered members:\n{member_list}", ephemeral=True
    )


@bot.slash_command(
    name="howmany", description="Show how many members are currently in the office"
)
async def how_many(interaction: discord.Interaction):
    """
    Show how many members are currently in the office.
    """
    count = len(office_attendees)
    await interaction.response.send_message(
        f"There are currently {count} members in the office.", ephemeral=True
    )


@bot.slash_command(
    name="help", description="Show instructions for using the office bot"
)
async def help_command(interaction: discord.Interaction):
    """
    Show help instructions for using the office bot.
    """
    embed = discord.Embed(
        title="🏢 Office Tracker Help",
        color=0x3498DB,
        description="Here's how to use the Office Tracker bot" ":",
    )

    embed.add_field(
        name="Checking In / Out",
        value="Use the buttons on the dashboard message:\n"
        "• **Entering 🟩** - Mark yourself as in the office\n"
        "• **Leaving 🟥** - Mark yourself as leaving\n"
        "• **Refresh 🔄** - Refresh the dashboard\n"
        "• **Clear All 🧹** - Clear all members",
        inline=False,
    )

    embed.add_field(
        name="Manual Commands",
        value="• `/setup` - Create the office dashboard (admin only)\n"
        "• `/add @User` - Add a user manually\n"
        "• `/remove @User` - Remove a user manually\n"
        "• `/howmany` - Show how many members are currently in the office\n"
        "• `/members` - Show all registered members\n",
        inline=False,
    )

    embed.set_footer(text="Use the commands only in the designated channel.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# -----------------------------
# Async TCP server for ESP32
# -----------------------------
async def handle_esp32(reader, writer):
    addr = writer.get_extra_info("peername")
    print(f"[ESP32] Connection from {addr}")
    try:
        data = await reader.readline()
        if not data:
            writer.close()
            await writer.wait_closed()
            return

        msg = data.decode().strip()
        print(f"[ESP32] Received: {msg}")

        # Only accept messages starting with 'uid:'
        if msg.startswith("uid:"):
            uid = msg[4:]  # everything after 'uid:'
            uid = uid.strip()
            if uid:  # non-empty UID
                print(f"[ESP32] Valid UID: {uid}")
                user_id = discord_id_from_uid(uid)
                name = members[user_id]["name"]
                if name is None:
                    print(f"[ESP32] Unknown UID: {uid}")
                    writer.write(b"error: unknown UID\n")
                    await writer.drain()
                    return
                print(f"[ESP32] User ID: {user_id}, Name: {name}")
                if name in office_attendees:
                    print(f"[ESP32] {name} is leaving the office.")
                    office_attendees.pop(name)
                else:
                    print(f"[ESP32] {name} is entering the office.")
                    office_attendees[name] = datetime.now()
                await refresh_dashboard(bot.get_guild(GUILD_ID))
                writer.write(b"ok\n")
            else:
                writer.write(b"error: empty UID\n")
        else:
            writer.write(b"error: invalid format, must start with 'uid:'\n")

        await writer.drain()
    except Exception as e:
        error_msg = f"error: {str(e)}\n"
        print(f"[ESP32] Exception: {e}")
        writer.write(error_msg.encode())
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()
        print(f"[ESP32] Connection closed from {addr}")


async def start_tcp_server():
    server = await asyncio.start_server(handle_esp32, "0.0.0.0", 9999)
    print("TCP server started on port 9999")
    async with server:
        await server.serve_forever()


# -----------------------------
# Ready Event
# -----------------------------
@bot.event
async def on_ready():
    bot.add_view(OfficeButtons())  # persistent buttons
    await bot.sync_commands()  # sync slash commands
    print(f"Logged in as {bot.user}")
    if RFID_ENABLED:
        bot.loop.create_task(start_tcp_server())  # start the TCP server in the background


# -----------------------------
# Run Bot
# -----------------------------
def run_bot():
    bot.run(TOKEN)


if __name__ == "__main__":
    run_bot()
