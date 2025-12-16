import requests
import json

url = "https://rumble.com/-livestream-api/get-data?key=a0-BV467nZuFmqgFm42KwGeWK86PvHB1frz3v76ejQDfCBAGcPZsUI_8fZRhAjNsNZIwV29savHpEO3NO0nFIA"

resp = requests.get(url)
print("STATUS:", resp.status_code)

data = resp.json()
print(json.dumps(data, indent=2))
