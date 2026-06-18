import requests

url = "https://rbidocs.rbi.org.in/rdocs/notification/PDFs/NT1438563868F652840A196CF1CB99CD36E53.PDF"

print(f"Downloading {url} ...")
r = requests.get(url)
print(f"Status: {r.status_code}")
print(f"Headers: {r.headers}")
print(f"First 10 bytes: {r.content[:10]}")
