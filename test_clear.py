import urllib.request
import json

# Test clear API
url = 'http://127.0.0.1:5000/api/db/clear'
data = json.dumps({"tables": ["scan_logs"]}).encode()
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
try:
    resp = urllib.request.urlopen(req)
    print(f"Status: {resp.status}")
    print(f"Body: {resp.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
