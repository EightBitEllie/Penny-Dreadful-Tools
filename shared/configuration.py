import ast
import inspect
import json
import os
import random
import re
import string
from typing import Any, Dict, List, Optional, Set, Union, overload

from shared.pd_exception import InvalidArgumentException
from shared.settings import BoolSetting, CONFIG, StrSetting, fail

try:
    import dotenv
    dotenv.load_dotenv('.')
except ImportError:
    print("Couldn't load .env")

RE_SUBKEY = re.compile(r'(\w+)\.(\w+)')


# On production, /rotation/ turns off when not active.
always_show_rotation = BoolSetting('always_show_rotation', False)

# Path to TSV list of card nicknames.  Should never be changed.  Used by magic.
card_alias_file = StrSetting('card_alias_file', './card_aliases.tsv')

# Block some of the more dangerous things from running if this is true
production = BoolSetting('production', False)
# Block Scryfall updates when things are broken
prevent_cards_db_updates = BoolSetting('prevent_cards_db_updates', False)


# Which format should checkmarks represent?
legality_format = StrSetting('legality_format', 'Penny Dreadful', configurable=True)

# Should !time use the 24-hour format?
use_24h = BoolSetting('use_24h', False, configurable=True)


DEFAULTS: Dict[str, Any] = {
    # Discord Webhook endpoint
    'bugs_webhook_id': None,
    'bugs_webhook_token': None,
    # Array of Pricefile URLs (foil, non-foil).  Used by price_grabber and rotation_script
    'cardhoarder_urls': [],

    # Path to chart storage directory.  Used by decksite.
    'charts_dir': './images/charts',
    # Is the codebase allowed to report github issues?  Disable on dev.
    'create_github_issues': True,
    # Google Custom Search Engine (for !google)
    'cse_api_key': None,
    'cse_engine_id': None,
    # mysql database name.  Used by decksite.
    'decksite_database': 'decksite',
    # mysql database name.  Used by decksite tests.
    'decksite_test_database': 'decksite_test',
    # URL for decksite API calls.  Used by discordbot.
    'decksite_hostname': 'pennydreadfulmagic.com',
    'decksite_port': 80,
    'decksite_protocol': 'https',
    # github credentials.  Used for auto-reporting issues.
    'github_password': None,
    'github_user': None,
    # Google Maps API key (for !time)
    'google_maps_api_key': None,
    # Required if you want to share cookies between subdomains
    'flask_cookie_domain': None,
    'flask_server_name': None,
    # Discord server id.  Used for admin verification.  Used by decksite.
    'guild_id': '207281932214599682',
    'image_dir': './images',
    'is_test_site': False,
    # Discord Webhook endpoint
    'league_webhook_id': None,
    'league_webhook_token': None,
    'legality_dir': '~/legality/Legality Checker/',
    'logsite_protocol': 'https',
    'logsite_hostname': 'logs.pennydreadfulmagic.com',
    'logsite_port': 80,
    'logsite_database': 'pdlogs',
    'magic_database': 'cards',
    'modo_bugs_dir': 'modo_bugs_repo',
    'mtgotraders_url': 'http://www.mtgotraders.com/pennydreadfull.php',
    'mysql_host': 'localhost',
    'mysql_passwd': '',
    'mysql_port': 3306,
    'mysql_user': 'pennydreadful',
    'not_pd': '',
    # Discord OAuth settings
    'oauth2_client_id': '',
    'oauth2_client_secret': '',
    'pdbot_api_token': lambda: ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(32)),
    'poeditor_api_key': None,
    'prices_database': 'prices',
    'pylint_threads': 4,
    'redis_db': 0,
    'redis_enabled': True,
    'redis_host': 'localhost',
    'redis_port': 6379,
    # Discord channel id to emit rotation-in-progress messages to.
    'rotation_hype_channel_id': '207281932214599682',
    'scratch_dir': '.',
    'sentry_token': None,
    'slow_fetch': 10.0,
    'slow_page': 10.0,
    'slow_query': 5.0,
    'slow_bot_start': 30,
    'test_vcr_record_mode': 'new_episodes',  # https://vcrpy.readthedocs.io/en/latest/usage.html#record-modes
    'to_password': '',
    'to_username': '',
    'tournament_channel_id': '334220558159970304',
    'tournament_reminders_channel_id': '207281932214599682',
    'typeahead_data_path': 'shared_web/static/dist/typeahead.json',
    'web_cache': '.web_cache',
    'whoosh_index_dir': 'whoosh_index',
    # Dreadrise top-level URL. used for dreadrise-based searches.
    # the first variable is used for requests, the second variable is used for links displayed to user
    'dreadrise_url': 'https://dreadrise.wizzerinus.tk',
    'dreadrise_public_url': 'https://dreadrise.wizzerinus.tk',
}

def get_optional_str(key: str) -> Optional[str]:
    val = get(key)
    if val is None:
        return None
    if isinstance(val, str):
        return val
    raise fail(key, val, str)

def get_str(key: str) -> str:
    val = get_optional_str(key)
    if val is None:
        raise fail(key, val, str)
    return val

def get_optional_int(key: str) -> Optional[int]:
    val = get(key)
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        # required so that we can pass int-values in environment variables
        CONFIG[key] = int(val)
        return CONFIG[key]
    raise fail(key, val, int)

def get_int(key: str) -> int:
    val = get_optional_int(key)
    if val is None:
        raise fail(key, val, int)
    return val

def get_float(key: str) -> Optional[float]:
    val = get(key)
    if val is None:
        return None
    if isinstance(val, float):
        return val
    if isinstance(val, int):
        return write(key, float(val))
    if isinstance(val, str):
        # required so that we can pass int-values in environment variables
        CONFIG[key] = float(val)
        return CONFIG[key]

    raise fail(key, val, float)

def get_list(key: str) -> List[str]:
    val = get(key)
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return val.split(',')
    raise fail(key, val, List[str])

def get_bool(key: str) -> bool:
    val = get(key)
    if val is None:
        raise fail(key, val, bool)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        # required so that we can pass bool-values in environment variables
        if val.lower() in ['true', 'yes', '1']:
            val = 'True'
        if val.lower() in ['false', 'no', '0']:
            val = 'False'
        val2 = ast.literal_eval(val)
        if isinstance(val2, bool):
            CONFIG[key] = val2
            return CONFIG[key]
    raise fail(key, val, bool)

def get(key: str) -> Optional[Union[str, List[str], int, float]]:
    if key in CONFIG:
        return CONFIG[key]
    subkey = RE_SUBKEY.match(key)
    if subkey:
        raise NotImplementedError()

    try:
        cfg = json.load(open('config.json'))
    except FileNotFoundError:
        cfg = {}
    if key in os.environ:
        cfg[key] = os.environ[key]
        print('CONFIG: {0}={1}'.format(key, cfg[key]))
        return cfg[key]
    if key in cfg:
        CONFIG.update(cfg)
        return cfg[key]
    if key in DEFAULTS:
        # Lock in the default value if we use it.
        cfg[key] = DEFAULTS[key]

        if inspect.isfunction(cfg[key]):  # If default value is a function, call it.
            cfg[key] = cfg[key]()
    else:
        raise InvalidArgumentException('No default or other configuration value available for {key}'.format(key=key))

    print('CONFIG: {0}={1}'.format(key, cfg[key]))
    fh = open('config.json', 'w')
    fh.write(json.dumps(cfg, indent=4, sort_keys=True))
    return cfg[key]


# pylint: disable=unused-argument, function-redefined
@overload
def write(key: str, value: str) -> str:
    pass

# pylint: disable=unused-argument, function-redefined
@overload
def write(key: str, value: int) -> int:
    pass

# pylint: disable=unused-argument, function-redefined
@overload
def write(key: str, value: float) -> float:
    pass

# pylint: disable=unused-argument, function-redefined
@overload
def write(key: str, value: Set[str]) -> Set[str]:
    pass

def write(key: str, value: Union[str, List[str], Set[str], int, float]) -> Union[str, List[str], Set[str], int, float]:
    subkey = RE_SUBKEY.match(key)
    filename = 'config.json'
    fullkey = key
    if subkey:
        filename = subkey.group(1) + '.config.json'
        key = subkey.group(2)

    try:
        cfg = json.load(open(filename))
    except FileNotFoundError:
        cfg = {}

    if isinstance(value, set):
        value = list(value)

    cfg[key] = value
    CONFIG[fullkey] = value

    print('CONFIG: {0}={1}'.format(fullkey, cfg[key]))
    fh = open(filename, 'w')
    fh.write(json.dumps(cfg, indent=4, sort_keys=True))
    return cfg[key]

def server_name() -> str:
    return get_str('decksite_hostname') + ':{port}'.format(port=get_int('decksite_port')) if get_optional_int('decksite_port') else ''
