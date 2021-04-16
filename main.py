import sys
import os
import glob

from discord.ext import commands
from discord import Intents

os.chdir(os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(1, os.getcwd())

with open("INSERT TOKEN HERE.txt", "r") as f:
    token = f.read()

os_slash = "\\" if sys.platform == "win32" else "/"

default_intents = Intents.default()

class Bot(commands.Bot):
    def __init__(self):
        self.prefix = "//"
        super().__init__(command_prefix=self.prefix, intents=default_intents, reconnect=True)

    def start_bot(self, token):
        print("Starting the cogs")
        self.load_commands()
        print("Launching the app...")
        self.run(token)

    async def on_ready(self):
        print("Bot is ready")

    def load_commands(self):
        cogs_file = glob.iglob(f"cogs{os_slash}**.py")
        for files in cogs_file:
            files = files.split(f"{os_slash}")[1][:-3]
            print(f"Launching {files} module")
            self.load_extension(f'cogs.{files}')

bot = Bot()
bot.start_bot(token)
