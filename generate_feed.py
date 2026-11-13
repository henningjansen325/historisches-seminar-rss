
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

BASE_URL = "https://www.hist.uni-heidelberg.de"
SOURCE_URL = (
    BASE_URL
    + "/de/historisches-seminar/einzelne-veranstaltungen"
)

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
        headers={
            "User-Agent": "HistorischesSeminarRSS/0.1"
        },
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
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

        title = title_element.get_text(" ", strip=True)
        time = field(link, "DateLine")
        description = field(link, "Description")
        location = field(link, "Location")

        # Datum aus der Veranstaltungs-URL auslesen
        match = re.search(
            r"(\d{4}-\d{2}-\d{2})(?:/|$)", href
        )
        event_date = None

        if match:
            try:
                event_date = datetime.strptime(
                    match.group(1), "%Y-%m-%d"
                )
            except ValueError:
                pass

        image = link.find("img")
        image_url = (
            urljoin(BASE_URL, image["src"])
            if image and image.get("src")
            else None
        )

        events.append({
            "title": title,
            "url": url,
            "date": event_date,
            "time": time,
            "description": description,
            "location": location,
            "image": image_url,
        })

    return events

def generate_feed(events):
    fg = FeedGenerator()
    fg.id(SOURCE_URL)
    fg.title("Historisches Seminar Heidelberg – Veranstaltungen")
    fg.link(href=SOURCE_URL, rel="alternate")
    fg.description(
        "Veranstaltungen des Historischen Seminars "
        "der Universität Heidelberg"
    )
    fg.language("de")

    for event in events:
        entry = fg.add_entry()
        entry.id(event["url"])
        entry.guid(event["url"], permalink=True)
        entry.title(event["title"])
        entry.link(href=event["url"])

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

    output = Path("public/feed.xml")
    output.parent.mkdir(parents=True, exist_ok=True)
    fg.rss_file(str(output), pretty=True)

    print(f"RSS-Datei erstellt: {output}")
    print(f"Anzahl Veranstaltungen: {len(events)}")

    for event in events:
        print("-", event["title"], event["url"])

if __name__ == "__main__":
    events = collect_events()

    if not events:
        raise RuntimeError(
            "Keine Veranstaltungen gefunden. "
            "Die HTML-Struktur muss geprüft werden."
        )

    generate_feed(events)
