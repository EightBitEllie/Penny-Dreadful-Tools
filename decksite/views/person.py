from typing import List

from flask import url_for

from decksite.data import person as ps
from decksite.view import View
from magic import tournaments
from magic.models import Card


# pylint: disable=no-self-use,too-many-instance-attributes
class Person(View):
    def __init__(self, person: ps.Person, cards: List[Card], only_played_cards: List[Card]) -> None:
        super().__init__()
        self.person = person
        self.decks = person.decks
        self.hide_person = True
        self.cards = cards
        self.only_played_cards = only_played_cards
        self.has_only_played_cards = len(self.only_played_cards) > 0
        for record in person.head_to_head:
            record.show_record = True
            record.opp_url = url_for('person', person_id=record.opp_mtgo_username)
        self.show_head_to_head = len(person.head_to_head) > 0
        self.tournament_organizer = self.person.name in [host for series in tournaments.all_series_info() for host in series['hosts']]
        self.show_seasons = True
        self.achievements_url = url_for('achievements')

    def __getattr__(self, attr):
        return getattr(self.person, attr)

    def page_title(self):
        return self.person.name
