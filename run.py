import importlib
import pkgutil
import sys
from typing import List


def run() -> None:
    if len(sys.argv) < 2:
        print('No entry point specified.')
        sys.exit(1)

    if 'discordbot' in sys.argv:
        from discordbot import bot
        bot.init()
    elif 'decksite' in sys.argv:
        from decksite import main
        main.init()
    elif 'decksite-profiler' in sys.argv:
        from werkzeug.contrib.profiler import ProfilerMiddleware
        from decksite import main
        main.APP.config['PROFILE'] = True
        main.APP.wsgi_app = ProfilerMiddleware(main.APP.wsgi_app, restrictions=[30]) # type: ignore
        main.init()
    elif 'price_grabber' in sys.argv:
        from price_grabber import price_grabber
        price_grabber.run()
    elif 'srv_price' in sys.argv:
        from price_grabber import srv_prices
        srv_prices.init()
    elif sys.argv[1] in ['scraper', 'scrapers', 'maintenance']:
        task(sys.argv)
    elif sys.argv[1] == 'tests':
        print('Call `dev.py tests` instead.')
        sys.exit(1)
    elif sys.argv[1] == 'rotation':
        from rotation_script import rotation_script
        rotation_script.run()
    elif sys.argv[1] == 'logsite':
        import logsite
        logsite.APP.run(host='0.0.0.0', port=5001, debug=True)
    else:
        try:
            m = importlib.import_module('{module}.main'.format(module=sys.argv[1]))
            m.run() # type: ignore
        except ImportError:
            print("I don't recognize `{0}`".format(sys.argv[1]))
            sys.exit(1)
    sys.exit(0)

def task(args: List[str]) -> None:
    module = args[1]
    if module == 'scraper':
        module = 'scrapers'
    if module == 'scrapers':
        module = 'decksite.scrapers'
    name = args.pop()
    from decksite.main import APP
    APP.config['SERVER_NAME'] = '127:0.0.1:5000'
    with APP.app_context():
        from magic import oracle, multiverse
        multiverse.init()
        if name != 'reprime_cache':
            oracle.init()
        if name == 'all':
            m = importlib.import_module('{module}'.format(module=module))
            # pylint: disable=unused-variable
            for importer, modname, ispkg in pkgutil.iter_modules(m.__path__): # type: ignore
                s = importlib.import_module('{module}.{name}'.format(name=modname, module=module))
                if getattr(s, 'scrape', None) is not None:
                    s.scrape() # type: ignore
                elif getattr(s, 'run', None) is not None:
                    s.run() # type: ignore
        else:
            s = importlib.import_module('{module}.{name}'.format(name=name, module=module))
            if getattr(s, 'scrape', None) is not None:
                s.scrape() # type: ignore
            elif getattr(s, 'run', None) is not None:
                s.run() # type: ignore
            # Only when called directly, not in 'all'
            elif getattr(s, 'ad_hoc', None) is not None:
                s.ad_hoc() # type: ignore

run()
