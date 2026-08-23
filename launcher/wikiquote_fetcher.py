"""
PyPottery Suite Launcher - Wikiquote Live Fetcher
Fetches live pop culture quotes from Wikiquote (en & it) MediaWiki API dynamically.
"""

import json
import logging
import random
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape
from typing import Optional

logger = logging.getLogger(__name__)

USER_AGENT = "PyPotteryLauncher/1.1 (https://github.com/lrncrd; contact@pypottery.org)"

# Pop culture, classic film, sci-fi, anime, and cult TV series articles on Wikiquote
POP_CULTURE_SOURCES = [
    # Italian Cult Series: Boris
    {"lang": "it", "title": "Boris", "source": "Boris"},
    {"lang": "it", "title": "Boris_(prima_stagione)", "source": "Boris (Stagione 1)"},
    {"lang": "it", "title": "Boris_(seconda_stagione)", "source": "Boris (Stagione 2)"},
    {"lang": "it", "title": "Boris_(terza_stagione)", "source": "Boris (Stagione 3)"},
    {"lang": "it", "title": "Boris_(quarta_stagione)", "source": "Boris (Stagione 4)"},
    {"lang": "it", "title": "Boris_-_Il_film", "source": "Boris - Il film"},

    # Cult Animation & Anime
    {"lang": "en", "title": "Neon Genesis Evangelion", "source": "Neon Genesis Evangelion"},
    {"lang": "en", "title": "Futurama/Season 1", "source": "Futurama"},
    {"lang": "en", "title": "Futurama/Season 2", "source": "Futurama"},
    {"lang": "en", "title": "Futurama/Season 3", "source": "Futurama"},
    {"lang": "en", "title": "Futurama/Season 4", "source": "Futurama"},

    # Classic Cinema & Sci-Fi
    {"lang": "en", "title": "Raiders of the Lost Ark", "source": "Raiders of the Lost Ark"},
    {"lang": "en", "title": "Indiana Jones and the Last Crusade", "source": "Indiana Jones and the Last Crusade"},
    {"lang": "en", "title": "Indiana Jones and the Temple of Doom", "source": "Indiana Jones and the Temple of Doom"},
    {"lang": "en", "title": "Back to the Future", "source": "Back to the Future"},
    {"lang": "en", "title": "Star Wars (film)", "source": "Star Wars"},
    {"lang": "en", "title": "The Empire Strikes Back", "source": "The Empire Strikes Back"},
    {"lang": "en", "title": "Return of the Jedi", "source": "Return of the Jedi"},
    {"lang": "en", "title": "Jurassic Park (film)", "source": "Jurassic Park"},
    {"lang": "en", "title": "The Matrix (film)", "source": "The Matrix"},
    {"lang": "en", "title": "The Terminator", "source": "The Terminator"},
    {"lang": "en", "title": "Terminator 2: Judgment Day", "source": "Terminator 2: Judgment Day"},
    {"lang": "en", "title": "The Lord of the Rings: The Fellowship of the Ring", "source": "The Lord of the Rings"},
    {"lang": "en", "title": "The Lord of the Rings: The Two Towers", "source": "The Lord of the Rings"},
    {"lang": "en", "title": "The Lord of the Rings: The Return of the King", "source": "The Lord of the Rings"},
    {"lang": "en", "title": "The Hobbit", "source": "The Hobbit"},
    {"lang": "en", "title": "Ghostbusters", "source": "Ghostbusters"},
    {"lang": "en", "title": "Blade Runner", "source": "Blade Runner"},
    {"lang": "en", "title": "The Big Lebowski", "source": "The Big Lebowski"},
    {"lang": "en", "title": "Groundhog Day (film)", "source": "Groundhog Day"},
    {"lang": "en", "title": "Monty Python and the Holy Grail", "source": "Monty Python and the Holy Grail"},
    {"lang": "en", "title": "Apollo 13 (film)", "source": "Apollo 13"},
    {"lang": "en", "title": "2001: A Space Odyssey (film)", "source": "2001: A Space Odyssey"},
    {"lang": "en", "title": "Alien (film)", "source": "Alien"},
    {"lang": "en", "title": "Aliens (film)", "source": "Aliens"},
    {"lang": "en", "title": "The Hitchhiker's Guide to the Galaxy (radio series)", "source": "The Hitchhiker's Guide to the Galaxy"},
    {"lang": "en", "title": "Dune (novel)", "source": "Dune"},
    {"lang": "en", "title": "Star Trek: The Next Generation", "source": "Star Trek: TNG"},
    {"lang": "en", "title": "Doctor Who", "source": "Doctor Who"},
    {"lang": "en", "title": "Toy Story", "source": "Toy Story"},
    {"lang": "en", "title": "Finding Nemo", "source": "Finding Nemo"},
    {"lang": "en", "title": "Spider-Man (2002 film)", "source": "Spider-Man"},
    {"lang": "en", "title": "The Dark Knight (film)", "source": "The Dark Knight"},
    {"lang": "en", "title": "Fight Club (film)", "source": "Fight Club"},
    {"lang": "en", "title": "Pulp Fiction", "source": "Pulp Fiction"},
    {"lang": "en", "title": "The Truman Show", "source": "The Truman Show"},
    {"lang": "en", "title": "Forrest Gump", "source": "Forrest Gump"},
    {"lang": "en", "title": "WALL-E", "source": "WALL-E"},
]

_POOL_LOCK = threading.Lock()
_QUOTES_POOL: list[dict] = []
_LAST_SERVED_INDEX: int = -1
_INITIAL_FETCH_DONE: bool = False


def clean_quote_text(raw_html: str) -> str:
    """Strip HTML tags and decode HTML entities."""
    # Convert <br> tags in dialogue to spaces
    text = re.sub(r"<br\s*/?>", " — ", raw_html)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(re.sub(r"\s+", " ", text)).strip()
    text = re.sub(r"^[\*\-\—\–\:\s]+", "", text).strip()
    text = re.sub(r"^\[.*?\]\s*", "", text).strip()
    return text


def parse_wikiquote_page(title: str, lang: str = "en") -> list[str]:
    """Fetch and extract quote lines from a given Wikiquote article title and language."""
    encoded = urllib.parse.quote(title)
    url = f"https://{lang}.wikiquote.org/w/api.php?action=parse&page={encoded}&prop=text&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    with urllib.request.urlopen(req, timeout=6) as response:
        data = json.loads(response.read().decode("utf-8"))
        html = data.get("parse", {}).get("text", {}).get("*", "")

        # Only take lines from dialogue / quote sections, cutting off metadata & navigation sections
        cutoffs = [
            'id="Citazioni_su',
            'id="Note',
            'id="Altri_progetti',
            'id="Bibliografia',
            'id="Voci_correlate',
            'id="Collegamenti_esterni',
            'id="Quotes_about',
            'id="Cast',
            'id="See_also',
            'id="External_links',
            'id="References',
        ]
        for cutoff in cutoffs:
            if cutoff in html:
                html = html.split(cutoff)[0]

        items = re.findall(r"<(?:li|dd|blockquote)>(.*?)</(?:li|dd|blockquote)>", html, re.DOTALL)
        valid_quotes = []
        for it in items:
            clean = clean_quote_text(it)
            if 20 <= len(clean) <= 240:
                if any(p in clean for p in [".", "!", "?", ",", "—", ":", "…"]):
                    if not any(
                        clean.startswith(x)
                        for x in [
                            "ISBN",
                            "http",
                            "Category",
                            "Categoria",
                            "See also",
                            "Voci correlate",
                            "External links",
                            "Collegamenti esterni",
                            "Main article",
                            "Voce principale",
                            "Retrieved",
                            "Photo",
                            "Seasons:",
                            "Stagioni:",
                            "Episodes:",
                            "Episodi:",
                            "Season ",
                            "Stagione ",
                            "Episodio ",
                            "Parte del cast",
                        ]
                    ):
                        if not re.match(r"^[A-Za-z\.\s]+[–—\-]\s*[A-Za-z\.\s]+$", clean):
                            valid_quotes.append(clean)
        return valid_quotes


def _fetch_quotes_batch(count: int = 4) -> list[dict]:
    """Fetches a fresh batch of quotes from random Wikiquote pages."""
    results = []
    sources = random.sample(POP_CULTURE_SOURCES, min(count, len(POP_CULTURE_SOURCES)))
    for src in sources:
        title = src["title"]
        lang = src.get("lang", "en")
        display_source = src.get("source", title)
        try:
            quotes = parse_wikiquote_page(title, lang=lang)
            url = f"https://{lang}.wikiquote.org/wiki/{urllib.parse.quote(title)}"
            for q in random.sample(quotes, min(6, len(quotes))):
                results.append({
                    "quote": q,
                    "source": display_source,
                    "origin": "Wikiquote",
                    "url": url,
                })
        except Exception as e:
            logger.debug("Error fetching Wikiquote page %s (%s): %s", title, lang, e)
            continue
    return results


def _populate_pool_background():
    """Background worker to fetch fresh quotes into the live memory pool."""
    global _QUOTES_POOL, _INITIAL_FETCH_DONE
    new_quotes = _fetch_quotes_batch(count=6)
    with _POOL_LOCK:
        if new_quotes:
            _QUOTES_POOL.extend(new_quotes)
            # Keep pool healthy and capped
            if len(_QUOTES_POOL) > 80:
                _QUOTES_POOL = _QUOTES_POOL[-80:]
        _INITIAL_FETCH_DONE = True


def fetch_live_wikiquote(force_refresh: bool = False) -> dict:
    """
    Returns a fresh live Wikiquote quote on each call / page reload.
    Uses an in-memory live pool for instant responses and spawns background replenishment.
    """
    global _QUOTES_POOL, _LAST_SERVED_INDEX

    with _POOL_LOCK:
        if _QUOTES_POOL and not force_refresh:
            # Pick a quote different from the last one served
            choices = [q for i, q in enumerate(_QUOTES_POOL) if i != _LAST_SERVED_INDEX]
            if choices:
                chosen = random.choice(choices)
                _LAST_SERVED_INDEX = _QUOTES_POOL.index(chosen)
                # If pool is running low, schedule background replenishment
                if len(_QUOTES_POOL) < 15:
                    threading.Thread(target=_populate_pool_background, daemon=True).start()
                return chosen

    # If pool is empty or force_refresh requested, fetch synchronously
    try:
        fresh_quotes = _fetch_quotes_batch(count=3)
        if fresh_quotes:
            with _POOL_LOCK:
                _QUOTES_POOL.extend(fresh_quotes)
                chosen = random.choice(fresh_quotes)
                _LAST_SERVED_INDEX = _QUOTES_POOL.index(chosen)
            return chosen
    except Exception as e:
        logger.debug("Failed fetching live quote: %s", e)

    # If pool already had items, fallback to one of them
    with _POOL_LOCK:
        if _QUOTES_POOL:
            return random.choice(_QUOTES_POOL)

    # Offline fallback
    fallbacks = [
        {
            "quote": "A cazzo di cane, maestro! Conto su di lei. A cazzo di cane!",
            "source": "Boris (Stagione 1)",
            "origin": "Wikiquote",
            "url": "https://it.wikiquote.org/wiki/Boris_(prima_stagione)",
        },
        {
            "quote": "Facciamoli scopare, così, de botto, senza senso. — Genio!",
            "source": "Boris (Stagione 1)",
            "origin": "Wikiquote",
            "url": "https://it.wikiquote.org/wiki/Boris_(prima_stagione)",
        },
        {
            "quote": "Non siatemi italiani, che oggi spacchiamo tutto!",
            "source": "Boris (Stagione 1)",
            "origin": "Wikiquote",
            "url": "https://it.wikiquote.org/wiki/Boris_(prima_stagione)",
        },
        {
            "quote": "Bender : I'm a bender. I bend girders, that's all I'm programmed to do.",
            "source": "Futurama",
            "origin": "Wikiquote",
            "url": "https://en.wikiquote.org/wiki/Futurama",
        },
    ]
    return random.choice(fallbacks)


# Initial background fetch on module import
threading.Thread(target=_populate_pool_background, daemon=True).start()
