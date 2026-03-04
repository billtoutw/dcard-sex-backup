import os
import json
import sqlite3
import cloudinary
import cloudinary.uploader
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from io import BytesIO

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

ZENROWS_API_KEY = os.getenv("ZENROWS_API_KEY")

DB_FILE = "dcard_backup.db"
BOARD = "sex"
LIKE_THRESHOLD = 30

def zenrows_get(url):
    payload = {
        "url": url,
        "apikey": ZENROWS_API_KEY,
        "js_render": "true",
        "antibot": "true",
        "premium_proxy": "true"
    }
    r = requests.get("https://api.zenrows.com/v1/", params=payload, timeout=40)
    return r.text

# （其餘程式碼與之前相同，為了篇幅我省略了，您可以保留原本的 backup 邏輯，只把抓取部分換成 zenrows_get）

# ...（如果您需要完整 main.py，請再告訴我，我馬上給您）
