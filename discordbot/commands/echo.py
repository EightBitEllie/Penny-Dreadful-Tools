from discord.ext import commands

from discordbot.command import MtgContext
from discordbot import emoji

@commands.command
async def echo(ctx: MtgContext, *, args: str) -> None:
    """Repeat after me…"""
    s = emoji.replace_emoji(args, ctx.bot)
    if not s:
        s = "I'm afraid I can't do that, Dave"
    await ctx.send(s)
