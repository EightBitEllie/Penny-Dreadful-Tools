import os

from flask import Flask, request, send_from_directory

from decksite.data import deck
from decksite.database import db
from decksite.views import AddForm, Deck, Home

APP = Flask(__name__)

@APP.teardown_appcontext
def close_db(error):
    # pylint: disable=unused-argument
    """Closes the database again at the end of the request."""
    db().close()

@APP.route('/')
def home():
    view = Home(deck.latest_decks())
    return view.page()

@APP.route('/decks/<deck_id>')
def decks(deck_id):
    view = Deck(deck.load_deck(deck_id))
    return view.page()

@APP.route('/add')
def add_form():
    view = AddForm()
    return view.page()

@APP.route('/add', methods=['POST'])
def add_deck():
    decks.add_deck(request.form)
    return add_form()


@APP.route('/querytappedout')
def deckcycle_tappedout():
    from decksite.scrapers import tappedout
    if not tappedout.is_authorised():
        tappedout.login()
    tappedout.fetch_decks('penny-dreadful')
    return home()

@APP.route('/favicon<rest>')
def favicon(rest):
    return send_from_directory(os.path.join(APP.root_path, 'static/images/favicon'), 'favicon{rest}'.format(rest=rest))

def init():
    APP.run(host='0.0.0.0', debug=True)
