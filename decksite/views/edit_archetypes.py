from decksite.data import deck
from decksite.view import View


# pylint: disable=no-self-use
class EditArchetypes(View):
    def __init__(self, archetypes, search_results, q, notq) -> None:
        super().__init__()
        self.archetypes = archetypes
        self.roots = [a for a in self.archetypes if a.is_root]
        self.queue = deck.load_decks(where='NOT d.reviewed', order_by='updated_date DESC')
        for d in self.queue:
            self.prepare_deck(d)
        self.has_search_results = len(search_results) > 0
        self.search_results = search_results
        for d in self.search_results:
            self.prepare_deck(d)
        self.q = q
        self.notq = notq

    def page_title(self):
        return 'Edit Archetypes'
