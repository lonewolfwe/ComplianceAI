import requests
from bs4 import BeautifulSoup

url = "https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx"
headers = {
    "User-Agent": "ComplianceAI/1.0 (MVP)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

response = requests.get(url, headers=headers)
print(f"Status Code: {response.status_code}")
soup = BeautifulSoup(response.text, "lxml")
tables = soup.select("table.tablebg")
print(f"Tables found: {len(tables)}")
if not tables:
    print(response.text[:500])
