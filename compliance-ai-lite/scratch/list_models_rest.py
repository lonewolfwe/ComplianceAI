import urllib.request
import json
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("NO API KEY")
    exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
req = urllib.request.urlopen(url)
data = json.loads(req.read().decode('utf-8'))

for m in data.get('models', []):
    methods = m.get('supportedGenerationMethods', [])
    if 'generateContent' in methods:
        print(f"Model: {m['name']} (version: {m.get('version')})")
