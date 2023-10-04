from typing import Any, Dict, List

from mypy_extensions import TypedDict
from typing_extensions import NotRequired

SetCode = str

# Type as returned by scryfall fetching
CardDescription = TypedDict('CardDescription', {
    # Parts we currently use …
    'all_parts': List[Dict[str, str]],
    'artist': str,
    'card_faces': List[Any],  # This should be List[CardDescription] but mypy doesn't support nested types yet.
    'cmc': float,
    'collector_number': str,
    'color_identity': List[str],
    'colors': List[str],
    'flavor_text': str,
    'hand_modifier': str,
    'id': str,
    'layout': str,
    'legalities': Dict[str, str],
    'life_modifier': str,
    'loyalty': str,
    'mana_cost': str,
    'oracle_text': str,
    'power': str,
    'name': str,
    'rarity': str,
    'reserved': bool,
    'set': str,
    'toughness': str,
    'type_line': str,
    'watermark': str,
    'flavor_name': NotRequired[str],

    # …and parts we don't. Some of these are typed other than str because of the usage in mutliverse_test which uses real data from Scryfall.
    'arena_id': str,
    'artist_ids': List[str],
    'booster': bool,
    'border_color': str,
    'card_back_id': str,
    'color_indicator': str,
    'digital': bool,
    'edhrec_rank': int,
    'foil': bool,
    'frame': str,
    'frame_effects': List[str],
    'full_art': bool,
    'games': List[str],
    'highres_image': bool,
    'illustration_id': str,
    'image_uris': Dict[str, str],
    'lang': str,
    'mtgo_foil_id': int,
    'mtgo_id': int,
    'multiverse_ids': List[int],
    'nonfoil': bool,
    'object': str,
    'oracle_id': str,
    'oversized': bool,
    'printed_name': str,
    'printed_text': str,
    'printed_type_line': str,
    'prints_search_uri': str,
    'promo': bool,
    'promo_types': List[str],
    'related_uris': Dict[str, str],
    'released_at': str,
    'reprint': bool,
    'rulings_uri': str,
    'scryfall_set_uri': str,
    'scryfall_uri': str,
    'set_name': str,
    'set_search_uri': str,
    'set_type': str,
    'set_uri': str,
    'story_spotlight': bool,
    'tcgplayer_id': int,
    'textless': bool,
    'uri': str,
    'variation': bool,
    'variation_of': str,
}, total=False)
