import requests
from bs4 import BeautifulSoup

url = "https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

response = requests.get(url, headers=headers, timeout=10)
response.raise_for_status()
soup = BeautifulSoup(response.text, "lxml")

tables = soup.select("table.tablebg")
with open("scratch/table_dump.html", "w", encoding="utf-8") as f:
    if tables:
        f.write(str(tables[0]))
        
        # also write all links in that table
        links = tables[0].find_all("a")
        f.write(f"\n\n--- Found {len(links)} links ---\n")
        for link in links:
            f.write(str(link) + "\n")
    else:
        f.write("No table.tablebg found.\n")
        f.write(str(soup))
