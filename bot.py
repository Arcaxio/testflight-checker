# main.py
import os
import discord
import asyncio
import requests
from discord.ext import commands
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
discord_bot_id = os.getenv("DISCORD_BOT_ID")
# Replace 'YOUR_BOT_TOKEN' with your actual Discord bot token.
BOT_TOKEN = discord_bot_id

# Time interval in seconds to check the links.
CHECK_INTERVAL = 60

# Dictionary of TestFlight links to monitor.
TESTFLIGHT_LINKS = {
    "Group A": "https://testflight.apple.com/join/rACTLjPL",
    "Group B": "https://testflight.apple.com/join/ocj3yptn",
    "Group C": "https://testflight.apple.com/join/CuMxZE2M",
    "Group D": "https://testflight.apple.com/join/T6qKfV6f",
    "Group E": "https://testflight.apple.com/join/sMm1MCYc",
}

# The text to look for to determine if the beta is full.
FULL_TEXT = "This beta is full."

# --- Bot Setup ---
# We need specific "intents" for the bot to work with DMs and commands.
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# We will store the IDs of subscribed users and test mode users in sets.
subscribed_users = set()
test_mode_users = set()

# The bot's command prefix is now 'testflight>'.
bot = commands.Bot(command_prefix='testflight>', intents=intents, help_command=None)

# --- Core Logic ---

async def check_links_and_notify():
    """
    This is the main background task. It checks the links and DMs users
    based on their subscription and test mode status.
    """
    await bot.wait_until_ready()
    print("Background task 'check_links_and_notify' has started.")

    while not bot.is_closed():
        if subscribed_users:
            print(f"Checking links for {len(subscribed_users)} subscribed user(s)...")

            all_status_messages = []
            slot_available_links = []

            for name, url in TESTFLIGHT_LINKS.items():
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
                    }
                    response = requests.get(url, headers=headers)
                    response.raise_for_status()

                    if FULL_TEXT in response.text:
                        message = f"**{name}**: Full."
                    else:
                        message = f"**{name}**: :tada: THERE IS A SLOT! <{url}>"
                        slot_available_links.append(message)
                    all_status_messages.append(message)

                except requests.exceptions.RequestException as e:
                    print(f"Error checking {name} ({url}): {e}")
                    all_status_messages.append(f"Could not check status for **{name}**. Error: {e}")

            # Prepare messages
            full_update_message = "--- Test Mode Status Update ---\n" + "\n".join(all_status_messages)
            slot_found = len(slot_available_links) > 0

            # Iterate over a copy of the set in case it changes during the loop.
            for user_id in list(subscribed_users):
                try:
                    user = await bot.fetch_user(user_id)
                    if not user: continue

                    # Send full update to test mode users regardless of status
                    if user_id in test_mode_users:
                        await user.send(full_update_message)
                    # Send update to normal users ONLY if a slot was found
                    elif slot_found:
                        slot_notification = "--- :tada: Slot Available! ---\n" + "\n".join(slot_available_links)
                        await user.send(slot_notification)

                except discord.errors.Forbidden:
                    print(f"Cannot send DM to user {user_id}. Removing from subscriptions.")
                    subscribed_users.discard(user_id)
                    test_mode_users.discard(user_id)
                except Exception as e:
                    print(f"An unexpected error occurred when sending DM to {user_id}: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


# --- Bot Events & Commands ---

@bot.event
async def on_ready():
    """
    This event is triggered once the bot successfully connects to Discord.
    """
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('Bot is ready to receive DMs.')
    print('------')
    bot.loop.create_task(check_links_and_notify())

@bot.event
async def on_message(message):
    """
    Handles messages that are not valid commands.
    """
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Only respond in DMs
    if isinstance(message.channel, discord.DMChannel):
        # If the message does not start with the prefix, it's not a command
        if not message.content.startswith(bot.command_prefix):
            await message.channel.send("Sorry, I don't quite understand that. If you need help, type `testflight>help`. Thank you!")

    # IMPORTANT: This line allows the bot to still process actual commands
    await bot.process_commands(message)

@bot.command()
async def notify(ctx):
    """Subscribes a user to receive TestFlight notifications."""
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("This command only works in my DMs! Please message me directly.")
        return

    user_id = ctx.author.id
    if user_id in subscribed_users:
        await ctx.send("You are already subscribed!")
    else:
        subscribed_users.add(user_id)
        print(f"User {ctx.author.name} (ID: {user_id}) has subscribed.")
        await ctx.send(
            "You have successfully subscribed! **By default, I will only message you when a slot opens.**\n\n"
            "To get a status message every minute (even if full), type `testflight>test-mode`.\n"
            "To unsubscribe, type `testflight>stop`."
        )

@bot.command(name='test-mode')
async def test_mode(ctx):
    """Toggles test mode for a user to receive all status updates."""
    if not isinstance(ctx.channel, discord.DMChannel): return

    user_id = ctx.author.id
    if user_id not in subscribed_users:
        await ctx.send("You need to subscribe first! Type `testflight>notify` to begin.")
        return

    if user_id in test_mode_users:
        test_mode_users.remove(user_id)
        await ctx.send("Test mode **disabled**. You will now only receive notifications when a slot is available.")
    else:
        test_mode_users.add(user_id)
        await ctx.send("Test mode **enabled**. You will now receive a status update every minute.")

@bot.command()
async def stop(ctx):
    """Unsubscribes a user from all notifications."""
    if not isinstance(ctx.channel, discord.DMChannel): return

    user_id = ctx.author.id
    if user_id in subscribed_users:
        subscribed_users.discard(user_id)
        test_mode_users.discard(user_id) # Also remove from test mode
        print(f"User {ctx.author.name} (ID: {user_id}) has unsubscribed.")
        await ctx.send("You have been unsubscribed. You will no longer receive updates.")
    else:
        await ctx.send("You are not currently subscribed.")

@bot.command()
async def help(ctx):
    """Shows the help message with all commands."""
    if not isinstance(ctx.channel, discord.DMChannel): return

    help_text = (
        "**Hello! I am the TestFlight Notifier Bot.** Here are my commands:\n\n"
        "`testflight>notify`\n"
        "Subscribes you to notifications. By default, I will only message you when a slot opens.\n\n"
        "`testflight>stop`\n"
        "Unsubscribes you from all notifications.\n\n"
        "`testflight>test-mode`\n"
        "Toggles test mode. When enabled, you will receive a status update every minute, regardless of whether slots are full or open.\n\n"
        "`testflight>help`\n"
        "Shows this help message."
    )
    await ctx.send(help_text)

# --- Run the Bot ---
if __name__ == "__main__":
    if BOT_TOKEN == 'YOUR_BOT_TOKEN':
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERROR: Please configure your BOT_TOKEN in the script.   !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    else:
        bot.run(BOT_TOKEN)
