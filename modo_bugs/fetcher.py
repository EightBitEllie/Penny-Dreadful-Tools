import json
import logging
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from bs4.element import Tag

from shared import fetch_tools, lazy

logger = logging.getLogger(__name__)

def search_scryfall(query: str) -> Tuple[int, List[str], List[str]]:
    """Returns a tuple. First member is an integer indicating how many cards match the query total,
       second member is a list of card names up to the maximum that could be fetched in a timely fashion."""
    if query == '':
        return 0, [], []
    logger.info(f'Searching scryfall for `{query}`')
    result_json = fetch_tools.fetch_json('https://api.scryfall.com/cards/search?q=' + fetch_tools.escape(query), character_encoding='utf-8')
    if 'code' in result_json.keys():  # The API returned an error
        if result_json['status'] == 404:  # No cards found
            return 0, [], []
        logger.error('Error fetching scryfall data:\n', result_json)
        return 0, [], []
    for warning in result_json.get('warnings', []):  # scryfall-provided human-readable warnings
        logger.warning(warning)
    result_data = result_json['data']
    result_data.sort(key=lambda x: x['legalities']['penny'])

    def get_frontside(scr_card: Dict) -> str:
        """If card is transform, returns first name. Otherwise, returns name.
        This is to make sure cards are later found in the database"""
        # not sure how to handle meld cards
        if scr_card['layout'] in ['transform', 'flip', 'modal_dfc']:
            return scr_card['card_faces'][0]['name']
        return scr_card['name']
    result_cardnames = [get_frontside(obj) for obj in result_data]
    return result_json['total_cards'], result_cardnames, result_json.get('warnings', [])

def catalog_cardnames() -> List[str]:
    result_json = fetch_tools.fetch_json('https://api.scryfall.com/catalog/card-names')
    names: List[str] = result_json['data']
    for n in names:
        if ' // ' in n:
            names.extend(n.split(' // '))
    return names

def update_redirect(file: str, title: str, redirect: str, **kwargs: str) -> bool:
    text = '---\ntitle: {title}\nredirect_to:\n - {url}\n'.format(title=title, url=redirect)
    for key, value in kwargs.items():
        text += f'{key}: {value}\n'
    text = text + '---\n'
    fname = f'{file}.md'
    if not os.path.exists(fname):
        bb_jekyl = open(fname, mode='w')
        bb_jekyl.write('')
        bb_jekyl.close()
    bb_jekyl = open(fname, mode='r')
    orig = bb_jekyl.read()
    bb_jekyl.close()
    if orig != text:
        logger.info(f'New {file} update!')
        bb_jekyl = open(fname, mode='w')
        bb_jekyl.write(text)
        bb_jekyl.close()
        return True
    if 'always-scrape' in sys.argv:
        return True
    return False

def find_announcements() -> Tuple[Optional[str], bool]:
    articles = [a for a in get_article_archive() if is_announcement(a)]
    if not articles:
        return (None, False)
    (title, link) = articles[0]
    logger.info('Found: {0} ({1})'.format(title, link))
    bn = 'PATCH NOTES' in fetch_tools.fetch(link)
    new = update_redirect('announcements', title, link, has_build_notes=str(bn))
    return (link, new)

def is_announcement(a: tuple[str, str]) -> bool:
    if a[0].startswith('Magic Online Weekly Announcements'):
        return True
    if a[0].startswith('Magic Online Announcements'):
        return True
    return False

def parse_article_item_extended(a: Tag) -> Tuple[Tag, str]:
    title = a.find_all('h3')[0]
    link = 'https://www.mtgo.com' + a.find_all('a')[0]['href']
    return (title, link)

@lazy.lazy_property
def get_article_archive() -> List[Tuple[str, str]]:
    try:
        html = fetch_tools.fetch('https://www.mtgo.com/archive')
    except fetch_tools.FetchException:
        html = fetch_tools.fetch('http://magic.wizards.com/en/articles/archive/')
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.find_all('a', class_='article-link')
    if links:
        return [parse_article_item_extended(a) for a in links]
    scripts = soup.find_all('script')
    findblob = re.compile(r'window.DGC.archive.articles = (.*?);', re.MULTILINE)
    for s in scripts:
        if (m := findblob.search(s.contents[0])):
            blob = m.group(1)
            j = json.loads(blob)
            return [(p['title'], 'https://www.mtgo.com/news/' + p['pageName']) for p in j]
    return []

def get_daybreak_label(url: str) -> str | None:
    html = fetch_tools.fetch(url)
    soup = BeautifulSoup(html, 'html.parser')
    label = soup.find('span', class_='label--primary')
    if label:
        return label.text
    return None
