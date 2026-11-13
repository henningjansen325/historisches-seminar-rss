
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

BASE_URL = "https://www.hist.uni-heidelberg.de"
SOURCE_URL = (
    BASE_URL
    + "/de/historisches-seminar/einzelne-veranstaltungen"
)

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


def date_from_heading(link):
    for heading in link.find_all_previous(
        ["h2", "h3"]
    ):
        text = heading.get_text(" ", strip=True)

        match = re.search(
            r"(\d{1,2})\.\s+"
            r"([A-Za-zÄÖÜäöüß]+)\s+"
            r"(\d{4})",
            text,
        )

        if match:
            day, month_name, year = match.groups()
            month = MONTHS.get(month_name)

            if month:
                try:
                    return datetime(
                        int(year), month, int(day)
                    ).date()
                except ValueError:
                    pass

    return None



def field(container, prefix):
    element = container.find(
        class_=lambda c: c and any(
            name.startswith(prefix)
            for name in (
                c if isinstance(c, list) else c.split()
            )
        )
    )
    return element.get_text(" ", strip=True) if element else ""


def collect_events():
    response = requests.get(
        SOURCE_URL,
        headers={"User-Agent": "HistorischesSeminarRSS/0.2"},
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    events = []
    seen = set()

    for link in soup.select(
        'a[href*="/einzelne-veranstaltungen/"]'

        event_date = date_from_heading(link)

        if event_date is None:
            match = re.search(
                r"(\d{4}-\d{2}-\d{2})(?:/|$)",
                href,
            )

            if match:
                try:
                    event_date = datetime.strptime(
                        match.group(1), "%Y-%m-%d"
                    ).date()
                    print(
                        "WARNUNG: Datum aus URL gelesen:",
                        url,
                    )
                except ValueError:
                    pass


        events.append({
            "title": title,
            "url": url,
            "date": event_date,
            "time": time_text,
            "description": description,
            "location": location,
            "image": image_url,
        })

    return events


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(
            encoding="utf-8"
        ))
    return {}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(
            state, ensure_ascii=False, indent=2,
            sort_keys=True
        ) + "\n",
        encoding="utf-8",
    )


def generate_feed(events, state):
    fg = FeedGenerator()
    fg.id(SOURCE_URL)
    fg.title(
        "Historisches Seminar Heidelberg – Veranstaltungen"
    )
    fg.link(href=SOURCE_URL, rel="alternate")
    fg.description(
        "Veranstaltungen des Historischen Seminars "
        "der Universität Heidelberg"
    )
    fg.language("de")

    now = datetime.now(timezone.utc)
    today = datetime.now(BERLIN).date()
    published = 0

    for event in events:
        # Vergangene Termine ausblenden
        if event["date"] and event["date"] < today:
            continue

        url = event["url"]

        if url not in state:
            state[url] = {
                "first_seen": now.isoformat()
            }

        entry = fg.add_entry()
        entry.id(url)
        entry.guid(url, permalink=True)
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
                + event["date"].strftime("%d.%m.%Y")
            )
        if event["time"]:
            parts.append("Uhrzeit: " + event["time"])
        if event["description"]:
            parts.append(event["description"])
        if event["location"]:
            parts.append("Ort: " + event["location"])
        if event["image"]:
            parts.append(
                '<img src="' + event["image"] + '" alt="">'
            )

        entry.description("<br>".join(parts))
        published += 1

    OUTPUT_FILE.parent.mkdir(
        parents=True, exist_ok=True
    )
    fg.rss_file(str(OUTPUT_FILE), pretty=True)

    save_state(state)

    print(f"RSS-Datei erstellt: {OUTPUT_FILE}")
    print(f"Veröffentlichte Veranstaltungen: {published}")
    print(f"Gespeicherte Kennungen: {len(state)}")


if __name__ == "__main__":
    events = collect_events()

    if not events:
        raise RuntimeError(
            "Keine Veranstaltungen gefunden. "
            "Bitte Quellseite prüfen."
        )

    state = load_state()
    generate_feed(events, state)
