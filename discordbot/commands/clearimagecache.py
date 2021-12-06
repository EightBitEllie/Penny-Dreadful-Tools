import glob
import os

from dis_snek.models.application_commands import slash_command
from discordbot import command

from discordbot.command import MtgContext
from shared import configuration


@slash_command('clearimagecache')
@command.slash_permission_pd_mods()
async def clearimagecache(ctx: MtgContext) -> None:
    """Deletes all the cached images.  Use sparingly"""
    image_dir = configuration.get('image_dir')
    if not image_dir:
        await ctx.send('Cowardly refusing to delete from unknown image_dir.')
        return
    files = glob.glob('{dir}/*.jpg'.format(dir=image_dir))
    for file in files:
        os.remove(file)
    await ctx.send('{n} cleared.'.format(n=len(files)))
