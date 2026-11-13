
import requests
from bs4 import BeautifulSoup

URL = (
    "https://www.hist.uni-heidelberg.de/de/"
    "historisches-seminar/einzelne-veranstaltungen"
)

response = requests.get(
    URL,
    headers={"User-Agent": "HistorischesSeminarRSS-Test/0.1"},
    timeout=30,
)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

print("HTTP-Status:", response.status_code)
print("Seitentitel:", soup.title.get_text(strip=True) if soup.title else "Keiner")
print("HTML-Größe:", len(response.content), "Bytes")

print("\n--- Überschriften ---")
for heading in soup.select("h1, h2, h3, h4")[:30]:
    print(heading.get_text(" ", strip=True))

print("\n--- Mögliche Veranstaltungslinks ---")
for link in soup.select("a[href]"):
    href = link.get("href", "")
    label = link.get_text(" ", strip=True)

    if label and any(
        term in href.lower()
        for term in ["veranstaltung", "event", "termin"]
    ):
        print(label[:120], "->", href)

print("\n--- Datumselemente ---")
for element in soup.select("time, [datetime]")[:30]:
    print(str(element)[:400])

print("\n--- Textvorschau ---")
main = soup.select_one("main") or soup.body
if main:
    print(main.get_text(" ", strip=True)[:3000])
    
print("\n--- Veranstaltungscontainer ---")

for link in soup.select('a[href*="/einzelne-veranstaltungen/"]'):
    href = link.get("href", "")

    if "?overlay=" in href:
        continue

    print("\nLINK:", href)
    print("HTML-STRUKTUR:")
    print(link.parent.prettify()[:5000])

print("\n--- Navigation / Pagination ---")
for element in soup.select(
    'a[rel="next"], .pager, .pagination, '
    '[data-page], [data-offset]'
):
    print(str(element)[:1000])

