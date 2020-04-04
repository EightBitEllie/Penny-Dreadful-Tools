from discord.ext import commands

from discordbot.command import MtgContext
from magic import multiverse
from shared import redis


@commands.command()
@commands.check(commands.is_owner())
async def rotate(ctx: MtgContext) -> None:
    """Perform all necessary post-rotation tasks."""
    await ctx.send('Rotating. This may take a while…')
    multiverse.init() # New Cards?
    await multiverse.set_legal_cards_async() # PD current list
    await multiverse.update_pd_legality_async() # PD previous lists
    if redis.REDIS: # Clear the redis cache
        redis.REDIS.flushdb()
    await ctx.send('Rotation complete. You probably want to restart me.')
