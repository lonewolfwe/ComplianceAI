import requests
from bs4 import BeautifulSoup

url = "https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx?Id=13514"
# The actual detail page usually is NotificationUser.aspx
url2 = "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=13514"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html",
}

for u in [url, url2]:
    print(f"\n--- Fetching {u} ---")
    try:
        r = requests.get(u, headers=headers)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            links = soup.find_all("a", href=True)
            pdfs = [link["href"] for link in links if ".pdf" in link["href"].lower()]
            print(f"Found {len(pdfs)} PDF links:")
            for p in pdfs[:3]:
                print(p)
            print("Preview of text:")
            print(soup.get_text()[:200].replace("\n", " "))
    except Exception as e:
        print(e)

