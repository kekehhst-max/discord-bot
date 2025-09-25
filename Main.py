import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
import threading
import os
import asyncio

intents = discord.Intents.default()
intents.members = True  # Required to ban users

bot = commands.Bot(command_prefix='/', intents=intents)

# --- Flask server to keep the bot alive ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    thread = threading.Thread(target=run)
    thread.start()


# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree  # Slash commands

reaction_roles = {}  # {message_id: {emoji: role_id}}

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")


# --- /dm Command ---
@tree.command(name="dm", description="Send a DM to a user")
@app_commands.describe(user="The user to DM", message="Message to send")
async def dm(interaction: discord.Interaction, user: discord.User, *, message: str):
    try:
        await user.send(message)
        await interaction.response.send_message(f"✅ Sent: '{message}' to {user.name}")
    except discord.Forbidden:
        await interaction.response.send_message("❌ Couldn't send DM. User may have DMs off.")


# --- /kick Command ---
@tree.command(name="kick", description="Kick a user from the server")
@app_commands.describe(member="The member to kick", reason="Reason for kicking")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("❌ You don't have permission to kick members.", ephemeral=True)
        return
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 {member} has been kicked. Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error kicking user: {e}")


# --- /timeout Command ---
@tree.command(name="timeout", description="Timeout a user for a certain duration")
@app_commands.describe(member="The member to timeout", duration="Duration in seconds", reason="Reason for timeout")
async def timeout(interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You don't have permission to timeout members.", ephemeral=True)
        return
    try:
        timeout_duration = discord.utils.utcnow() + discord.timedelta(seconds=duration)
        await member.timeout(timeout_duration, reason=reason)
        await interaction.response.send_message(f"⏲️ {member} has been timed out for {duration} seconds. Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error timing out user: {e}")


# --- /announce Command ---
@tree.command(name="announce", description="Send an announcement to all members in the server")
@app_commands.describe(message="The message to send to all members")
async def announce(interaction: discord.Interaction, message: str):
    # Check if user has administrator permission
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ You don't have permission to make announcements.", ephemeral=True
        )
        return

    # Defer the interaction immediately to avoid timeout
    await interaction.response.defer(ephemeral=True)

    sent_count = 0
    failed_count = 0

    # Send DMs in small batches to avoid rate limits
    for member in interaction.guild.members:
        # Skip bots
        if member.bot:
            continue
        try:
            await member.send(message)
            sent_count += 1
        except discord.Forbidden:
            failed_count += 1
        except discord.HTTPException:
            # Handle temporary sending errors by waiting
            await asyncio.sleep(1)
            try:
                await member.send(message)
                sent_count += 1
            except:
                failed_count += 1
        await asyncio.sleep(0.5)  # small delay between messages to prevent rate limit

    # Report results
    await interaction.followup.send(
        f"✅ Announcement sent to {sent_count} members.\n"
        f"⚠️ Could not send to {failed_count} members (DMs off or other error)."
    )


# --- /dailypoll Command ---
@tree.command(name="dailypoll", description="Post a daily poll in the channel")
async def dailypoll(interaction: discord.Interaction, *, message: str):
    embed = discord.Embed(description=message)
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Your poll has been posted!", ephemeral=True)


# --- /selfroleadd Command ---
@tree.command(name="selfroleadd", description="Create a reaction role message")
@app_commands.describe(
    message="The message users will see",
    emoji1="First emoji",
    role1="Role for first emoji",
    emoji2="Second emoji (optional)",
    role2="Role for second emoji (optional)"
)
async def selfroleadd(
    interaction: discord.Interaction,
    message: str,
    emoji1: str,
    role1: discord.Role,
    emoji2: str = None,
    role2: discord.Role = None
):
    sent = await interaction.channel.send(message)
    await sent.add_reaction(emoji1)
    if emoji2:
        await sent.add_reaction(emoji2)

    # Store reaction-role mapping
    reaction_roles[sent.id] = {emoji1: role1.id}
    if emoji2 and role2:
        reaction_roles[sent.id][emoji2] = role2.id

    await interaction.response.send_message("✅ Reaction role message created!", ephemeral=True)

# Slash command: /post
@bot.tree.command(name="post", description="Send a post with an image")
@app_commands.describe(
    title="The title of your post (supports # for big letters)",
    description="The message to display (optional)",
    image_url="Direct link to an image (jpg, png, gif)"
)
async def post(
    interaction: discord.Interaction,
    title: str,
    description: str = None,     # now optional
    image_url: str = None
):
    # Build the embed text
    content = title
    if description:  # only add if provided
        content += "\n\n" + description

    embed = discord.Embed(description=content, color=0x00ffcc)
    if image_url:
        embed.set_image(url="https://i.ibb.co/XZ080phr/WELCOME-1.png")

    # Acknowledge the interaction silently
    await interaction.response.defer(ephemeral=True)
    # Send the embed as a normal message (not a reply)
    await interaction.channel.send(embed=embed)


# --- /ban Command ---
@tree.command(name="ban", description="Ban a user from the server")
@app_commands.describe(member="The member to ban", reason="Reason for banning")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ You don't have permission to ban members.", ephemeral=True)
        return

    # Standard message to send before banning
    dm_message = (
        f"You have been banned from **{interaction.guild.name}** for violating our rules.\n"
        "If you believe this was a mistake, please contact a moderator or use the appeal form. https://discord.gg/KdAUxTHKtC "
    )

    try:
        await member.send(dm_message)
    except discord.Forbidden:
        await interaction.response.send_message("⚠️ Could not send DM. Proceeding with the ban...", ephemeral=True)

    await interaction.guild.ban(member, reason=reason)
    await interaction.response.send_message(f"🔨 {member.mention} has been banned.")


# --- Reaction Events ---
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    emoji = str(payload.emoji)
    msg_id = payload.message_id
    if msg_id in reaction_roles and emoji in reaction_roles[msg_id]:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(reaction_roles[msg_id][emoji])
        if role:
            member = payload.member
            await member.add_roles(role)


@bot.event
async def on_raw_reaction_remove(payload):
    emoji = str(payload.emoji)
    msg_id = payload.message_id
    if msg_id in reaction_roles and emoji in reaction_roles[msg_id]:
        guild = bot.get_guild(payload.guild_id)
        member = await guild.fetch_member(payload.user_id)
        role = guild.get_role(reaction_roles[msg_id][emoji])
        if role:
            await member.remove_roles(role)


# --- Ticket Closure Logic (Optional from your code) ---
TICKET_CATEGORIES = [
    1370906367023382619, 1370769885801615512, 1370776143883534336
]

async def send_ticket_closure_question():
    for guild in bot.guilds:
        for category_id in TICKET_CATEGORIES:
            category = discord.utils.get(guild.categories, id=category_id)
            if category:
                for channel in category.text_channels:
                    if isinstance(channel, discord.TextChannel):
                        last_message = await channel.history(limit=1).flatten()
                        if not last_message or (
                            discord.utils.utcnow() - last_message[0].created_at
                        ).days >= 1:
                            closure_message = await channel.send("Can this ticket be closed?")
                            await monitor_ticket_closure(closure_message)

async def monitor_ticket_closure(message: discord.Message):
    try:
        def check(m):
            return m.channel == message.channel and any(word in m.content.lower() for word in ['yes', 'yepp', 'sure'])

        while True:
            response = await bot.wait_for('message', check=check, timeout=43200)
            if response:
                await message.channel.send("Ticket will be closed in 5 minutes.")
                await asyncio.sleep(300)
                await message.channel.delete()
                break
    except asyncio.TimeoutError:
        await message.channel.send("Closing the ticket due to inactivity.")
        await asyncio.sleep(300)
        await message.channel.delete()


# --- Run the Bot ---
keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
