from typing import List

from decksite.data.archetype import Archetype
from decksite.view import View
from magic.models import Deck
from shared.container import Container


# pylint: disable=no-self-use, too-many-instance-attributes, too-many-arguments
class EditRules(View):
    def __init__(self,
                 num_classified: int,
                 num_total: int,
                 doubled_decks: List[Deck],
                 mistagged_decks: List[Deck],
                 overlooked_decks: List[Deck],
                 rules: List[Container],
                 archetypes: List[Archetype]) -> None:
        super().__init__()
        self.num_classified = num_classified
        self.num_total = num_total
        self.doubled_decks = doubled_decks
        self.mistagged_decks = mistagged_decks
        self.overlooked_decks = overlooked_decks
        self.rules = rules
        self.archetypes = archetypes
        self.rules.sort(key=lambda c: c.archetype_name)
        for d in self.doubled_decks:
            self.prepare_deck(d)
        for d in self.mistagged_decks:
            self.prepare_deck(d)
        for d in self.overlooked_decks:
            self.prepare_deck(d)
        self.has_doubled_decks = len(self.doubled_decks) > 0
        self.has_mistagged_decks = len(self.mistagged_decks) > 0
        self.has_overlooked_decks = len(self.overlooked_decks) > 0

    def page_title(self):
        return 'Edit Rules'
