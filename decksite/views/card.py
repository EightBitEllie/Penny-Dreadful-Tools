from decksite.view import View
from magic import legality, rotation


# pylint: disable=no-self-use
class Card(View):
    def __init__(self, card) -> None:
        super().__init__()
        self.card = card
        self.cards = [card]
        self.decks = card.decks
        self.legal_formats = card.legalities.keys()
        self.show_seasons = True

    def __getattr__(self, attr):
        return getattr(self.card, attr)

    def page_title(self):
        return self.card.name
