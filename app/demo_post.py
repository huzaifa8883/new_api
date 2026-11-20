import os
import random
import requests

# Client script: sends data to the API running on the VPS.
BASE_URL = os.environ.get("CARD_API_URL", "http://72.61.146.237:5005")
URL = f"{BASE_URL}/api/card"

for i in range(10):
    r = requests.post(URL, json={"count": random.randint(1, 50)}, timeout=10)
    print(r.json())
