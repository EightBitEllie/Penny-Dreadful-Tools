import datetime
import urllib.parse
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

import pydantic

from decksite.data import archetype, competition, deck, match, person, top
from decksite.database import db
from magic import decklist
from shared import dtutil, fetch_tools
from shared.database import  sqlescape
from shared.pd_exception import InvalidArgumentException, InvalidDataException


Card = str
Cards = Dict[Card, int]
DeckID = int
GatherlingUsername = str
FinalStandings = Dict[GatherlingUsername, int]
MTGOUsername = str

class Bool(Enum):
    TRUE = 1
    FALSE = 0

class Wins(Enum):
    ZERO = 0
    ONE = 1
    TWO = 2

class Timing(Enum):
    MAIN = 1
    FINALS = 2

class Structure(Enum):
    SINGLE_ELIMINATION = 'Single Elimination'
    SWISS_BLOSSOM = 'Swiss (Blossom)'
    SWISS = 'Swiss'
    LEAGUE = 'League'
    LEAGUE_MATCH = 'League Match'

class Verification(Enum):
    VERIFIED = "verified"
    UNVERIFIED = None # Not actually sure what value shows when a match is not verified.

class Medal(Enum):
    WINNER = '1st'
    RUNNER_UP = '2nd'
    TOP_4 = 't4'
    TOP_8 = 't8'

class Archetype(Enum):
    AGGRO = "Aggro"
    CONTROL = "Control"
    COMBO = "Combo"
    AGGRO_CONTROL = "Aggro-Control"
    AGGRO_COMBO = "Aggro-Combo"
    COMBO_CONTROL = "Combo-Control"
    RAMP = "Ramp"
    MIDRANGE = "Midrange"
    UNCLASSIFIED = "Unclassified"

@pydantic.dataclasses.dataclass
class GatherlingMatch:
    id: int
    playera: GatherlingUsername
    playera_wins: Wins
    playerb: GatherlingUsername
    playerb_wins: Wins
    timing: Timing
    round: int
    verification: Verification

@pydantic.dataclasses.dataclass
class GatherlingDeck:
    id: DeckID
    found: Bool
    playername: GatherlingUsername
    name: str
    archetype: Archetype
    notes: str
    maindeck: Cards
    sideboard: Cards

@pydantic.dataclasses.dataclass
class Finalist:
    medal: Medal
    player: GatherlingUsername
    deck: DeckID

@pydantic.dataclasses.dataclass
class Standing:
    player: GatherlingUsername
    active: Bool
    score: int
    matches_played: int
    matches_won: int
    draws: int
    games_won: int
    games_played: int
    byes: int
    OP_Match: str
    PL_Game: str
    OP_Game: str
    seed: int

@pydantic.dataclasses.dataclass()
class Player:
    name: GatherlingUsername
    verified: Optional[Literal[True]]
    discord_id: Optional[int]
    discord_handle: Optional[str]
    mtga_username: Optional[str]
    mtgo_username: Optional[MTGOUsername]

@pydantic.dataclasses.dataclass()
class Event:
    series: str
    season: int
    number: int
    host: str
    cohost: Optional[str]
    active: Bool
    finalized: Bool
    current_round: int
    start: str
    mainrounds: int
    mainstruct: str
    finalrounds: int
    finalstruct: str
    mtgo_room: str
    matches: List[GatherlingMatch]
    unreported: List[str]
    decks: List[GatherlingDeck]
    finalists: List[Finalist]
    standings: List[Standing]
    players: Dict[GatherlingUsername, Player]

APIResponse = Dict[str, Event]

ALIASES: Dict[str, str] = {}

def scrape() -> None:
    data = fetch_tools.fetch_json(gatherling_url('/api.php?action=recent_events'))
    response = make_api_response(data)
    process(response)

def make_api_response(data: Dict[str, Dict[Any, Any]]) -> APIResponse:
    response = {}
    for k, v in data.items():
        # First check it's a series we are interested in.
        if is_interesting_series(v['series']):
            response[k] = Event(**v)
    return response

def is_interesting_series(name: str):
    return len(db().select('SELECT id FROM competition_series WHERE name = %s', [name])) > 0

def process(response: APIResponse) -> None:
    for name, event in response.items():
        process_tournament(name, event)

def process_tournament(name: str, event: Event):
    db().begin('tournament')
    name_safe = sqlescape(name)
    cs = competition.load_competitions(f'c.name = {name_safe}')
    if len(cs) > 0:
        return # We already have this tournament, no-op out of here.
    try:
        date = vivify_date(event.start)
    except ValueError:
        raise InvalidDataException(f"Could not parse tournament date `{event.start}`")
    fs = determine_finishes(event.standings, event.finalists)
    competition_id = insert_competition(name, date, event)
    decks_by_gatherling_username = insert_decks(competition_id, date, event.decks, fs, list(event.players.values()))
    insert_matches(date, decks_by_gatherling_username, event.matches, event.mainrounds + event.finalrounds)
    guess_archetypes(list(decks_by_gatherling_username.values()))
    db().commit('tournament')

def determine_finishes(standings: List[Standing], finalists: List[Finalist]) -> FinalStandings:
    ps = {}
    for f in finalists:
        ps[f.player] = medal2finish(f.medal)
    r = len(ps)
    for p in standings:
        if p.player not in ps.keys():
            r += 1
            ps[p.player] = r
    return ps

def medal2finish(m: Medal):
    if m == Medal.WINNER:
        return 1
    elif m == Medal.RUNNER_UP:
        return 2
    elif m == Medal.TOP_4:
        return 3
    elif m == Medal.TOP_8:
        return 5
    raise InvalidArgumentException(f"I don't know what the finish is for `{m}`")

def insert_competition(name: str, date: datetime.datetime, event: Event) -> int:
    if not name or not event.start or event.finalrounds is None or not event.series:
        raise InvalidDataException(f'Unable to insert Gatherling tournament `{name}` with `{event}`')
    url = gatherling_url('/eventreport.php?event=' + urllib.parse.quote(name))
    if event.finalrounds == 0:
        top_n = top.Top.NONE
    else:
        try:
            top_n = top.Top(pow(2, event.finalrounds))
        except ValueError:
            raise InvalidDataException(f'Unexpected number of finalrounds: `{event.finalrounds}`')
    return competition.get_or_insert_competition(date, date, name, event.series, url, top_n)

def insert_decks(competition_id: int, date: datetime.datetime, ds: List[GatherlingDeck], fs: FinalStandings, players: List[Player]) -> Dict[GatherlingUsername, deck.Deck]:
    return {d.playername: insert_deck(competition_id, date, d, fs, players) for d in ds}

def insert_deck(competition_id: int, date: datetime.datetime, d: GatherlingDeck, fs: FinalStandings, players: List[Player]) -> deck.Deck:
    finish = fuzzy_get(fs, d.playername)
    if not finish:
        raise InvalidDataException(f"I don't have a finish for `{d.playername}`")
    mtgo_username = find_mtgo_username(d.playername, players)
    if not mtgo_username:
        raise InvalidDataException(f"I don't have an MTGO username for `{d.playername}`")
    raw = {
        'name': d.name,
        'source': 'Gatherling',
        'competition_id': competition_id,
        'created_date': dtutil.dt2ts(date),
        'mtgo_username': mtgo_username,
        'finish': finish,
        'url': gatherling_url(f'deck.php?mode=view&id={d.id}'),
        'archetype': d.archetype,
        'identifier': d.id,
        'cards': {'maindeck': d.maindeck, 'sideboard': d.sideboard},
    }
    if len(raw['cards']['maindeck']) + len(raw['cards']['sideboard']) == 0:
        raise InvalidDataException(f'Unable to add deck with no cards `{d.id}`')
    try:
        decklist.vivify(raw['cards'])
    except InvalidDataException:
        raise
    if deck.get_deck_id(raw['source'], raw['identifier']):
        raise InvalidArgumentException("You asked me to insert a deck that already exists `{raw['source']}`, `{raw['identifier']}`")
    return deck.add_deck(raw)

def insert_matches(date: datetime.datetime, decks_by_gatherling_username: Dict[GatherlingUsername, deck.Deck], ms: List[GatherlingMatch], total_rounds: int):
    for m in ms:
        insert_match(date, decks_by_gatherling_username, m, total_rounds)

def insert_match(date: datetime.datetime, decks_by_gatherling_username: Dict[GatherlingUsername, deck.Deck], m: GatherlingMatch, total_rounds: int):
    d1 = fuzzy_get(decks_by_gatherling_username, m.playera)
    if not d1:
        raise InvalidDataException(f"I don't have a deck for `{m.playera}`")
    if is_bye(m):
        d2_id = None
        player2_wins = 0
    else:
        d2 = fuzzy_get(decks_by_gatherling_username, m.playerb)
        if not d2:
            raise InvalidDataException(f"I don't have a deck for `{m.playerb}`")
        d2_id = d2.id
        player2_wins = m.playerb_wins.value
    match.insert_match(date, d1.id, m.playera_wins.value, d2_id, player2_wins, m.round, elimination(m, total_rounds))

# Account for the Gatherling API's slightly eccentric representation of byes.
def is_bye(m: GatherlingMatch):
    return m.playera == m.playerb and m.playera_wins == Wins.ZERO and m.playerb_wins == Wins.ZERO

# 'elimination' is an optional int with meaning: NULL = nontournament, 0 = Swiss, 8 = QF, 4 = SF, 2 = F
def elimination(m: GatherlingMatch, total_rounds: int):
    if m.timing != Timing.FINALS:
        return 0
    remaining_rounds = total_rounds - m.round + 1
    return pow(2, remaining_rounds) # 1 => 2, 2 => 4, 3 => 8 which are the values 'elimination' expects

def find_mtgo_username(gatherling_username: GatherlingUsername, players: List[Player]):
    for p in players:
        if p.name == gatherling_username:
            if p.mtgo_username is not None:
                return aliased(p.mtgo_username)
    return aliased(gatherling_username) # Best guess given that we don't know for certain

def gatherling_url(href: str) -> str:
    if href.startswith('http'):
        return href
    return 'https://gatherling.com{href}'.format(href=href)

def guess_archetypes(ds: List[deck.Deck]) -> None:
    deck.calculate_similar_decks(ds)
    for d in ds:
        if d.similar_decks and d.similar_decks[0].archetype_id is not None:
            archetype.assign(d.id, d.similar_decks[0].archetype_id, None, False)

def rankings(soup: BeautifulSoup) -> List[str]:
    rows = soup.find(text='Current Standings').find_parent('table').find_all('tr')

    # Expected structure:
    # <td colspan="8"><h6> Penny Dreadful Thursdays 1.02</h6></td>
    # <td>Rank</td>, <td>Player</td>, <td>Match Points</td>, <td>OMW %</td>, <td>PGW %</td>, <td>OGW %</td>, <td>Matches Played</td>, <td>Byes</td>
    # <td colspan="8"><br/><b> Tiebreakers Explained </b><p></p></td>
    # <td colspan="8"> Players with the same number of match points are ranked based on three tiebreakers scores according to DCI rules. In order, they are: </td>
    # <td colspan="8"> OMW % is the average percentage of matches your opponents have won. </td>
    # <td colspan="8"> PGW % is the percentage of games you have won. </td>
    # <td colspan="8"> OGW % is the average percentage of games your opponents have won. </td>
    # <td colspan="8"> BYEs are not included when calculating standings. For example, a player with one BYE, one win, and one loss has a match win percentage of .50 rather than .66</td>
    # <td colspan="8"> When calculating standings, any opponent with less than a .33 win percentage is calculated as .33</td>

    rows = rows[2:-7]
    ranks = []
    for row in rows:
        cells = row.find_all('td')
        mtgo_username = aliased(cells[1].string)
        ranks.append(mtgo_username)
    return ranks

def medal_winners(s: str) -> Dict[str, int]:
    winners = {}
    # The HTML of this page is so badly malformed that BeautifulSoup cannot really help us with this bit.
    rows = re.findall('<tr style=">(.*?)</tr>', s, re.MULTILINE | re.DOTALL)
    for row in rows:
        player = BeautifulSoup(row, 'html.parser').find_all('td')[2]
        if player.find('img'):
            mtgo_username = aliased(player.a.contents[0])
            img = re.sub(r'styles/Chandra/images/(.*?)\.png', r'\1', player.img['src'])
            if img == WINNER:
                winners[mtgo_username] = 1
            elif img == SECOND:
                winners[mtgo_username] = 2
            elif img == TOP_4:
                winners[mtgo_username] = 3
            elif img == TOP_8:
                winners[mtgo_username] = 5
            elif img == 'verified':
                pass
            else:
                raise InvalidDataException('Unknown player image `{img}`'.format(img=img))
    return winners

def finishes(winners: Dict[str, int], ranks: List[str]) -> Dict[str, int]:
    final = winners.copy()
    r = len(final)
    for p in ranks:
        if p not in final.keys():
            r += 1
            final[p] = r
    return final

def tournament_deck(cells: ResultSet, competition_id: int, date: datetime.datetime, final: Dict[str, int]) -> Optional[deck.Deck]:
    d: deck.RawDeckDescription = {'source': 'Gatherling', 'competition_id': competition_id, 'created_date': dtutil.dt2ts(date)}
    player = cells[2]
    username = aliased(player.a.contents[0].string)
    d['mtgo_username'] = username
    d['finish'] = final.get(username)
    if d['finish'] is None:
        raise InvalidDataException(f'{username} has no finish')
    link = cells[4].a
    d['url'] = gatherling_url(link['href'])
    d['name'] = link.string
    if cells[5].find('a'):
        d['archetype'] = cells[5].a.string
    else:
        d['archetype'] = cells[5].string
    gatherling_id = urllib.parse.parse_qs(urllib.parse.urlparse(str(d['url'])).query)['id'][0]
    d['identifier'] = gatherling_id
    existing = deck.get_deck_id(d['source'], d['identifier'])
    if existing is not None:
        return deck.load_deck(existing)
    dlist = decklist.parse(fetch_tools.post(gatherling_url('deckdl.php'), {'id': gatherling_id}))
    d['cards'] = dlist
    if len(dlist['maindeck']) + len(dlist['sideboard']) == 0:
        logger.warning('Rejecting deck with id {id} because it has no cards.'.format(id=gatherling_id))
        return None
    return deck.add_deck(d)

def tournament_matches(d: deck.Deck) -> List[bs4.element.Tag]:
    url = 'https://gatherling.com/deck.php?mode=view&id={identifier}'.format(identifier=d.identifier)
    s = fetch_tools.fetch(url, character_encoding='utf-8', retry=True)
    soup = BeautifulSoup(s, 'html.parser')
    anchor = soup.find(string='MATCHUPS')
    if anchor is None:
        logger.warning('Skipping {id} because it has no MATCHUPS.'.format(id=d.id))
        return []
    table = anchor.findParents('table')[0]
    rows = table.find_all('tr')
    rows.pop(0) # skip header
    rows.pop() # skip empty last row
    return find_matches(d, rows)

MatchListType = List[Dict[str, Any]]

def find_matches(d: deck.Deck, rows: ResultSet) -> MatchListType:
    matches = []
    for row in rows:
        tds = row.find_all('td')
        if 'No matches were found for this deck' in tds[0].renderContents().decode('utf-8'):
            logger.warning('Skipping {identifier} because it played no matches.'.format(identifier=d.identifier))
            break
        round_type, num = re.findall(r'([TR])(\d+)', tds[0].string)[0]
        num = int(num)
        if round_type == 'R':
            elimination = 0
            round_num = num
        elif round_type == 'T':
            elimination = num
            round_num += 1
        else:
            raise InvalidDataException('Round was neither Swiss (R) nor Top 4/8 (T) in {round_type} for {id}'.format(round_type=round_type, id=d.id))
        if 'Bye' in tds[1].renderContents().decode('utf-8') or 'No Deck Found' in tds[5].renderContents().decode('utf-8'):
            left_games, right_games, right_identifier = 2, 0, None
        else:
            left_games, right_games = tds[2].string.split(' - ')
            href = tds[5].find('a')['href']
            right_identifier = re.findall(r'id=(\d+)', href)[0]
        matches.append({
            'round': round_num,
            'elimination': elimination,
            'left_games': left_games,
            'left_identifier': d.identifier,
            'right_games': right_games,
            'right_identifier': right_identifier
        })
    return matches

def insert_matches_without_dupes(dt: datetime.datetime, matches: MatchListType) -> None:
    db().begin('insert_matches_without_dupes')
    inserted: Dict[str, bool] = {}
    for m in matches:
        reverse_key = str(m['round']) + '|' + str(m['right_id']) + '|' + str(m['left_id'])
        if inserted.get(reverse_key):
            continue
        match.insert_match(dt, m['left_id'], m['left_games'], m['right_id'], m['right_games'], m['round'], m['elimination'])
        key = str(m['round']) + '|' + str(m['left_id']) + '|' + str(m['right_id'])
        inserted[key] = True
    db().commit('insert_matches_without_dupes')

def add_ids(matches: MatchListType, ds: List[deck.Deck]) -> None:
    decks_by_identifier = {d.identifier: d for d in ds}
    def lookup(gatherling_id: int) -> deck.Deck:
        try:
            return decks_by_identifier[gatherling_id]
        except KeyError as c:
            raise InvalidDataException("Unable to find deck with gatherling id '{0}'".format(gatherling_id)) from c
    for m in matches:
        m['left_id'] = lookup(m['left_identifier']).id
        m['right_id'] = lookup(m['right_identifier']).id if m['right_identifier'] else None

def gatherling_url(href: str) -> str:
    if href.startswith('http'):
        return href
    return 'https://gatherling.com/{href}'.format(href=href)

def aliased(username: str) -> str:
    if not ALIASES:
        load_aliases()
    return ALIASES.get(username, username)

def load_aliases() -> None:
    ALIASES['dummyplaceholder'] = '' # To prevent doing the load on every lookup if there are no aliases in the db.
    for entry in person.load_aliases():
        ALIASES[entry.alias] = entry.mtgo_username
