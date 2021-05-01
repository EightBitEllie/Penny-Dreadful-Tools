import datetime

import pytest

from magic import tournaments
from shared import dtutil


# pylint: disable=invalid-name
@pytest.mark.xfail(reason='The code this is testing will only ever rename the current season')
def test_get_all_next_tournament_dates() -> None:
    just_before_s19_kick_off = datetime.datetime(2021, 2, 19).astimezone(tz=dtutil.WOTC_TZ)
    just_after_s19_kick_off = datetime.datetime(2021, 2, 21).astimezone(tz=dtutil.WOTC_TZ)
    info = tournaments.get_all_next_tournament_dates(just_before_s19_kick_off)
    assert info[0][1] == 'Penny Dreadful FNM'
    assert info[1][1] == 'Season Kick Off'
    info = tournaments.get_all_next_tournament_dates(just_after_s19_kick_off)
    assert info[-1][1] == 'Penny Dreadful Thursdays'
