import logging
import os
import asyncpraw
import re
import random

import discord
from discord.ext import commands
from discord import app_commands

from util.vars.eind_vars import *
from dotenv import load_dotenv
from util.vars.periodic_reminders import TOP_REDDIT_CAT_DT
from aiocron import crontab

SUBREDDIT_REGEX = "(?<!reddit.com)\/r\/[a-zA-Z0-9]{3,}"
I_REDDIT_REGEX = "https:\/\/i.redd.it\/[a-zA-Z0-9]*\.(png|jpg)"
I_IMGUR_REGEX = "https:\/\/i.imgur.com/[a-zA-Z0-9]*\.(png|jpg)"
CHANNEL_ID = int(os.getenv("ANIMALS_CHANNEL_ID"))
CATS = "cats"


class Reddit(commands.Cog):

    reddit = asyncpraw.Reddit(
        client_id=os.getenv("REDDIT_ID"),
        client_secret=os.getenv("REDDIT_SECRET"),
        user_agent=REDDIT_USER_AGENT
    )

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info(f"[{__name__}] Cog is ready")
        crontab(TOP_REDDIT_CAT_DT, func=self.schedule_cat_pic, start=True)
        # await self.schedule_cat_pic()

    def __init__(self, bot: discord.Client):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if message.channel.name in CHANNEL_IGNORE_LIST:
            return

        message_content = message.content.lower()
        matches = re.findall(SUBREDDIT_REGEX, message_content)

        if matches:
            await self.handle_reddit_matches(matches, message)

        return

    @app_commands.command(name="randomcat", description="Sends a random cat picture off of reddit")
    async def send_random_cat(self, interaction: discord.Interaction):
        await interaction.response.send_message(await self.get_random_image_post(CAT_SUBREDDITS))
        return

    @app_commands.command(name="randomdog", description="Sends a random dog picture off of reddit")
    async def send_random_dog(self, interaction: discord.Interaction):
        await interaction.response.send_message(await self.get_random_image_post(DOG_SUBREDDITS))
        return

    async def get_random_image_post(self, subreddit_list):
        chosen_sub = random.choice(subreddit_list)
        sub = await self.reddit.subreddit(chosen_sub)
        posts = [post async for post in sub.hot(limit=20)]
        chosen_post = posts[random.randint(0,len(posts)-1)]
        while not re.match(I_REDDIT_REGEX, chosen_post.url) and not re.match(I_IMGUR_REGEX, chosen_post.url):
            chosen_post = random.choice(posts)
        return chosen_post.url

    async def schedule_cat_pic(self):
        channel = await self.bot.fetch_channel(CHANNEL_ID)
        subreddit = await self.reddit.subreddit(CATS)
        async for submission in subreddit.top("day", limit=1):
            post = submission
        title = f"**Top post on /r/cats today: {post.title}**"
        description = post.url
        payload = f"{title}\n{description}"

        await channel.send(payload)
        return

    async def handle_reddit_matches(self, matches, message):
        plural = "s" if len(matches) > 1 else ""
        payload = f"Found {len(matches)} subreddit link{plural} in your message:\n"
        safe_matches = await self.get_safe_matches(matches)

        if not safe_matches:
            return

        for match in safe_matches:
            payload = payload + f"https://www.reddit.com{match}\n"

        await message.reply(payload)
        return

    async def get_safe_matches(self, matches):
        safe_matches = []
        for match in matches:
            subreddit = await self.reddit.subreddit(match[3:], fetch=True)
            if not subreddit.over18:
                safe_matches.append(match)

        return safe_matches


async def setup(bot):
    await bot.add_cog(Reddit(bot))
