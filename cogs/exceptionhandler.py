import traceback

import discord
from discord.ext import commands

from bot import Eindjeboss


class ExceptionHandler(commands.Cog):

    def __init__(self, bot: Eindjeboss):
        self.bot = bot
        self.bot.tree.error(coro=self.__dispatch_to_app_command_handler)

    async def __dispatch_to_app_command_handler(self, interaction, error):
        self.bot.dispatch("app_command_error", interaction, error)

    @commands.Cog.listener()
    async def on_app_command_error(self, intr: discord.Interaction,
                                   err: discord.app_commands.AppCommandError):
        user = await self.bot.fetch_user(self.bot.owner_id)
        stacktrace = ''.join(traceback.format_exception(None, err, None))
        msg = "Exception in command **/%s**\n```logs\n%s```"
        await user.send(msg % (intr.command.name, stacktrace))
        await intr.response.send_message(
            "Something went wrong. Please try again later.", ephemeral=True)


async def setup(client: commands.Bot):
    await client.add_cog(ExceptionHandler(client))
