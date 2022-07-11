from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from naff.client import Client
from naff.models import Extension, OptionTypes, slash_command, slash_option
from naff.models.discord.enums import MessageFlags

from discordbot import command
from discordbot.command import MtgContext
from shared import configuration


class Google(Extension):
    @slash_command('google')
    @slash_option('query', 'Search terms', OptionTypes.STRING, required=True)
    async def google(self, ctx: MtgContext, query: str) -> None:
        """Google search"""
        api_key = configuration.cse_api_key.value
        cse_id = configuration.cse_engine_id.value
        if not api_key or not cse_id:
            await ctx.send('The google command has not been configured.', flags=MessageFlags.EPHEMERAL)
            return

        if len(query) == 0:
            await ctx.send('{author}: No search term provided. Please type !google followed by what you would like to search.'.format(author=ctx.author.mention), flags=MessageFlags.EPHEMERAL)
            return

        try:
            service = build('customsearch', 'v1', developerKey=api_key)
            res = service.cse().list(q=query, cx=cse_id, num=1).execute()  # pylint: disable=no-member
            if 'items' in res:
                r = res['items'][0]
                s = '{title} <{url}> {abstract}'.format(title=r['title'], url=r['link'], abstract=r['snippet'])
            else:
                s = '{author}: Nothing found on Google.'.format(author=ctx.author.mention)
        except HttpError as e:
            if e.resp['status'] == '403':
                s = 'We have reached the allowed limits of Google API'
            else:
                raise

        await ctx.send(s)

    m_google = command.alias_message_command_to_slash_command(google, 'query')

def setup(bot: Client) -> None:
    Google(bot)
