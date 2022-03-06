from typing import Any, Dict, List, Optional, Tuple, Union

import pytest
from _pytest.mark.structures import ParameterSet
from dis_snek import Snake
from dis_snek.models import BaseCommand, Context

from discordbot.bot import Bot
from discordbot.command import MtgMixin
from shared.container import Container


@pytest.fixture(scope='module')
def discordbot() -> Bot:
    bot = Bot()
    return bot

class ContextForTests(Context, MtgMixin):
    sent = False
    sent_args = False
    sent_file = False
    content: Optional[str] = None
    bot: Snake = None

    async def send(self, content: Optional[str] = None, *args: Any, **kwargs: Any) -> None:  # pylint: disable=signature-differs
        self.sent = True
        self.sent_args = bool(args)
        self.sent_file = 'file' in kwargs.keys()
        self.sent_embed = 'embed' in kwargs.keys()
        self.content = content

    async def trigger_typing(self) -> None:
        ...

def get_params() -> List[Union[ParameterSet, Tuple[str, dict[str, Any], Optional[str], Optional[str]]]]:
    return [
        ('art', {'card': 'Island'}, None, None),
        ('barbs', {}, None, None),
        # ('echo', {'args': 'test string!'}, None, None),
        ('explain', {'thing': None}, None, None),
        ('explain', {'thing': 'bugs'}, None, None),
        ('flavor', {'card': 'Falling Star'}, 'No flavor text available', None),  # No flavor
        ('flavor', {'card': 'Dwarven Pony'}, 'likes to eat meat', None),  # Meaty flavor
        ('flavor', {'card': 'Gruesome Menagerie|grn'}, 'Variety is also the spice of death.', None),  # Spicy flavor
        ('flavor', {'card': 'capital offense|UST'}, 'part basket case, all lowercase.', None),  # Capital flavor
        ('flavor', {'card': 'Reliquary Tower|plg20'}, 'Archmage Vintra', None),  # Long set code
        ('history', {'card': 'Necropotence'}, None, None),
        ('legal', {'card': 'Island'}, None, None),
        ('legal', {'card': 'Black Lotus'}, None, None),
        ('oracle', {'card': 'Dark Ritual'}, None, None),
        pytest.param('p1p1', {}, None, None, marks=pytest.mark.functional),
        ('patreon', {}, None, None),
        ('price', {'card': 'Gleemox'}, None, None),
        ('rotation', {}, None, None),
        pytest.param('rhinos', {}, None, None, marks=pytest.mark.functional),
        ('rulings', {'card': 'Worldknit'}, None, None),
        ('scry', {'query': 'f:pd'}, None, None),
        ('status', {}, None, None),
        ('time', {'place': 'AEST'}, None, None),
        ('tournament', {}, None, None),
        ('version', {}, None, None),
        ('whois', {'args': 'silasary'}, None, 'whois'),
        ('whois', {'args': 'kaet'}, None, 'whois'),
        # ('whois', {'args': '<@154363842451734528>'}, None, 'whois'),
        # ('whois', {'args': '<@!224755717767299072>'}, None, 'whois'),
    ]


@pytest.mark.functional
@pytest.mark.asyncio
@pytest.mark.parametrize('cmd, kwargs, expected_content, function_name', get_params())
async def test_command(discordbot: Snake, cmd: str, kwargs: Dict[str, Any], expected_content: str, function_name: str) -> None:
    command = find_command(discordbot, cmd, function_name)
    print(f'command: {command}')

    ctx = ContextForTests()
    ctx._client = discordbot
    ctx.id = 1
    ctx.bot = discordbot
    ctx.channel = Container({'id': '1'})
    ctx.channel.send = ctx.send
    ctx.channel.trigger_typing = ctx.trigger_typing
    ctx.message = Container()
    ctx.message.channel = ctx.channel
    ctx.author = Container()
    ctx.author.mention = '<@111111111111>'
    ctx.kwargs = kwargs
    ctx.args = []
    ctx.content_parameters = kwargs.get('args', '')
    await command(ctx, **kwargs)
    assert ctx.sent
    if expected_content is not None and ctx.content is not None:
        assert expected_content in ctx.content

def find_command(discordbot: Snake, cmd: str, function_name: str = None) -> BaseCommand:
    command = None
    for cmds in discordbot.interactions.values():
        if cmd in cmds:
            command = cmds[cmd]
            print(f'found command {command} - {command.callback}')
            if function_name and command.callback.__name__ == function_name:
                return command
            if not function_name:
                break
    else:
        command = discordbot.commands[cmd]
        print(f'found command {command} - {command.callback}')
    return command
