
import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

BASE_URL = "https://www.hist.uni-heidelberg.de"
SOURCE_URL = BASE_URL + "/de/historisches-seminar/einzelne-veranstaltungen"
STATE_FILE = Path("events_state.json")
OUTPUT_FILE = Path("public/feed.xml")
BERLIN = ZoneInfo("Europe/Berlin")

MONTHS = {
    "Januar": 1,
    "Februar": 2,
    "März": 3,
    "April": 4,
    "Mai": 5,
    "Juni": 6,
    "Juli": 7,
    "August": 8,
    "September": 9,
    "Oktober": 10,
    "November": 11,
    "Dezember": 12,
}

DATE_PATTERN = re.compile(
    r"\b(\d{1,2})\.\s*([A-Za-zÄÖÜäöüß]+)\s+(\d{4})\b"
)
URL_DATE_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2})(?:/|$)"
)


def field(container, prefix):
    element = container.find(
        class_=lambda classes: classes and any(
            name.startswith(prefix)
            for name in (
                classes
                if isinstance(classes, list)
                else classes.split()
            )
        )
    )
    return (
        element.get_text(" ", strip=True)
        if element else ""
    )


def date_from_heading(link):
    # Die nächstgelegene vorherige Datumsüberschrift suchen.
    for heading in link.find_all_previous(["h2", "h3"]):
        text = heading.get_text(" ", strip=True)
        match = DATE_PATTERN.search(text)

        if not match:
            continue

        day, month_name, year = match.groups()
        month = MONTHS.get(month_name)

        if month:
            try:
                return datetime(
                    int(year), month, int(day)
                ).date()
            except ValueError:
                continue

    return None


def date_from_url(url):
    match = URL_DATE_PATTERN.search(
        urlparse(url).path
    )

    if match:
        try:
            return datetime.strptime(
                match.group(1), "%Y-%m-%d"
            ).date()
        except ValueError:
            pass

    return None


def collect_events():
    response = requests.get(
        SOURCE_URL,
        headers={
            "User-Agent": "HistorischesSeminarRSS/0.3"
        },
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(
        response.text, "html.parser"
    )

    events = []
    seen = set()

    for link in soup.select(
        'a[href*="/einzelne-veranstaltungen/"]'
    ):
        href = link.get("href", "")
        title_element = link.find("h3")

        if not title_element or "?overlay=" in href:
            continue

        url = urljoin(BASE_URL, href)

        if url in seen:
            continue

        seen.add(url)

        event_date = date_from_heading(link)

        if event_date is None:
            event_date = date_from_url(url)
            print(
                "WARNUNG: Datum aus URL gelesen:",
                url,
            )

        image = link.find("img")
        image_url = (
            urljoin(BASE_URL, image["src"])
            if image and image.get("src")
            else None
        )

        events.append({
            "title": title_element.get_text(
                " ", strip=True
            ),
            "url": url,
            "date": event_date,
            "time": field(link, "DateLine"),
            "description": field(
                link, "Description"
            ),
            "location": field(
                link, "Location"
            ),
            "image": image_url,
        })

    return events


def load_state():
    if STATE_FILE.exists():
        return json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

    return {}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )


def generate_feed(events, state):
    fg = FeedGenerator()

    fg.id(SOURCE_URL)
    fg.title(
        "Historisches Seminar Heidelberg – Veranstaltungen"
    )
    fg.link(
        href=SOURCE_URL,
        rel="alternate",
    )
    fg.description(
        "Veranstaltungen des Historischen Seminars "
        "der Universität Heidelberg"
    )
    fg.language("de")

    now = datetime.now(timezone.utc)
    today = datetime.now(BERLIN).date()
    published = 0

    for event in events:
        # Vergangene Veranstaltungen ausblenden.
        if (
            event["date"]
            and event["date"] < today
        ):
            continue

        url = event["url"]

        # Erstmaliges Erkennen dauerhaft speichern.
        if url not in state:
            state[url] = {
                "first_seen": now.isoformat()
            }

        entry = fg.add_entry()

        entry.id(url)
        entry.guid(
            url,
            permalink=True,
        )
        entry.title(event["title"])
        entry.link(href=url)

        first_seen = datetime.fromisoformat(
            state[url]["first_seen"]
        )
        entry.pubDate(first_seen)

        parts = []

        if event["date"]:
            parts.append(
                "Datum: "
                + event["date"].strftime(
                    "%d.%m.%Y"
                )
            )

        if event["time"]:
            parts.append(
                "Uhrzeit: "
                + escape(event["time"])
            )

        if event["description"]:
            parts.append(
                escape(event["description"])
            )

        if event["location"]:
            parts.append(
                "Ort: "
                + escape(event["location"])
            )

        if event["image"]:
            parts.append(
                '<img src="'
                + escape(
                    event["image"],
                    quote=True,
                )
                + '" alt="">'
            )

        entry.description(
            "<br>".join(parts)
        )

        published += 1

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fg.rss_file(
        str(OUTPUT_FILE),
        pretty=True,
    )

    save_state(state)

    print(
        f"RSS-Datei erstellt: {OUTPUT_FILE}"
    )
    print(
        f"Veröffentlichte Veranstaltungen: {published}"
    )
    print(
        f"Gespeicherte Kennungen: {len(state)}"
    )


if __name__ == "__main__":
    events = collect_events()

    if not events:
        print(
            "HINWEIS: Keine Veranstaltungen gefunden; "
            "leerer Feed wird erstellt."
        )

    state = load_state()
    generate_feed(events, state)
