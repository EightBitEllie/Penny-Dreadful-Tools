from naff.models import prefixed_command, slash_command

from discordbot.command import MtgContext
from magic import seasons


@slash_command('rotation')
async def nextrotation(ctx: MtgContext) -> None:
    """Date of the next Penny Dreadful rotation."""
    await ctx.send(seasons.message())

m_rotation = prefixed_command('rotation')(nextrotation.callback)
m_ro = prefixed_command('ro')(nextrotation.callback)
