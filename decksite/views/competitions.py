from typing import List

from decksite.view import View
from magic.models import Competition


# pylint: disable=no-self-use
class Competitions(View):
    def __init__(self, competitions: List[Competition]) -> None:
        super().__init__()
        self.competitions = competitions
        self.show_seasons = True

    def page_title(self) -> str:
        return 'Competitions'
