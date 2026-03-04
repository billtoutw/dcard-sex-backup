import os
import json
import sqlite3
import cloudinary
import cloudinary.uploader
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from io import BytesIO

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

DB_FILE = "dcard_backup.db"
BOARD = "sex"
LIKE_THRESHOLD = 30

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""CREATE TABLE IF NOT EXISTS posts (id TEXT PRIMARY KEY, title TEXT, content TEXT, like_count INTEGER, image_urls TEXT, backup_time TEXT)""")
    conn.commit()
    conn.close()
init_db()

def backup():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"https://www.dcard.tw/f/{BOARD}", wait_until="networkidle")
        
        posts = page.evaluate('''() => {
            return Array.from(document.querySelectorAll('a[href*="/p/"]')).slice(0, 30).map(a => {
                const m = a.href.match(/p\\/(\\d+)/);
                return m ? {id: m[1]} : null;
            }).filter(Boolean);
        }''')

        for post in posts:
            post_id = post['id']
            page.goto(f"https://www.dcard.tw/f/{BOARD}/p/{post_id}", wait_until="networkidle")
            
            data = page.evaluate('''() => ({
                title: document.querySelector("h1")?.innerText || "無標題",
                content: document.querySelector("main")?.innerHTML || "",
                media: Array.from(document.querySelectorAll("img[src], video[src]")).map(el => el.src)
            })''')
            
            title = data["title"]
            content = data["content"]
            media_urls = []
            for url in data["media"]:
                if url:
                    try:
                        uploaded = cloudinary.uploader.upload(url, resource_type="auto", timeout=30)["secure_url"]
                        media_urls.append(uploaded)
                    except:
                        pass
            
            conn = sqlite3.connect(DB_FILE)
            conn.execute("INSERT INTO posts VALUES (?,?,?,?,?,?)", 
                        (post_id, title, content, 9999, json.dumps(media_urls), datetime.now().isoformat()))
            conn.commit()
            conn.close()
            print(f"✅ 已備份：{title}")
        
        browser.close()

if __name__ == "__main__":
    backup()
