import discord
from discord.ext import commands, voice_recv
import speech_recognition as sr
import asyncio
import threading

# ============================================================
# CONFIG
# ============================================================
import os
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Words to detect (lowercase)
BANNED_WORDS = [
    "nigga",
    "nigger",
]
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

counters = {}  # {user_id: count}

class MySink(voice_recv.AudioSink):
    def __init__(self, text_channel):
        self.text_channel = text_channel
        self.recognizer = sr.Recognizer()
        self.buffers = {}

    def wants_opus(self):
        return False

    def write(self, user, data):
        if user is None:
            return
        if user.id not in self.buffers:
            self.buffers[user.id] = {"user": user, "frames": []}
        self.buffers[user.id]["frames"].append(data.pcm)

        if len(self.buffers[user.id]["frames"]) >= 50:
            frames = b"".join(self.buffers[user.id]["frames"])
            self.buffers[user.id]["frames"] = []
            threading.Thread(
                target=self.process_audio,
                args=(user, frames),
                daemon=True
            ).start()

    def process_audio(self, user, frames):
        try:
            audio = sr.AudioData(frames, 48000, 2)
            text = self.recognizer.recognize_google(audio).lower()
            print(f"{user.name} said: {text}")
            if any(word in text for word in BANNED_WORDS):
                counters[user.id] = counters.get(user.id, 0) + 1
                count = counters[user.id]
                asyncio.run_coroutine_threadsafe(
                    self.text_channel.send(
                        f"🚨 {user.mention} has said the word **{count}** time(s)!"
                    ),
                    bot.loop
                )
        except sr.UnknownValueError:
            pass
        except Exception as e:
            print(f"Error: {e}")

    def cleanup(self):
        self.buffers.clear()

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

@bot.command()
async def join(ctx):
    if ctx.author.voice is None:
        await ctx.send("You need to be in a voice channel first!")
        return
    channel = ctx.author.voice.channel
    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect(cls=voice_recv.VoiceRecvClient)
    sink = MySink(ctx.channel)
    ctx.voice_client.listen(sink)
    await ctx.send(f"Joined **{channel.name}** and now listening! 👂")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop_listening()
        await ctx.voice_client.disconnect()
        await ctx.send("Left the voice channel.")
    else:
        await ctx.send("I'm not in a voice channel.")

@bot.command()
async def stats(ctx):
    if not counters:
        await ctx.send("No counts yet!")
        return
    msg = "**Word Counter Stats:**\n"
    for user_id, count in counters.items():
        user = bot.get_user(user_id)
        name = user.name if user else f"User {user_id}"
        msg += f"- {name}: **{count}** time(s)\n"
    await ctx.send(msg)

@bot.command()
async def reset(ctx):
    counters.clear()
    await ctx.send("Counters reset! ✅")

bot.run(BOT_TOKEN)
