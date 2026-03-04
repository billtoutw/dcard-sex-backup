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

def normalize_url(url):
    if not url: return None
    if url.startswith("//"): return f"https:{url}"
    if url.startswith("/"): return f"https://www.dcard.tw{url}"
    return url

def upload_to_cloudinary(url):
    url = normalize_url(url)
    if not url: return None
    headers = {"Referer": "https://www.dcard.tw/"}
    try:
        return cloudinary.uploader.upload(url, headers=headers, resource_type="auto", timeout=30)["secure_url"]
    except:
        try:
            import requests
            r = requests.get(url, headers=headers, timeout=20)
            r.raise_for_status()
            file_obj = BytesIO(r.content)
            file_obj.name = "media.bin"
            return cloudinary.uploader.upload(file_obj, resource_type="auto", timeout=30)["secure_url"]
        except:
            return None

def backup():
    print("🔄 開始備份（先產生測試文章讓您看到效果）")
    # 強制產生測試文章
    test_posts = [
        ("測試文章 1 - 西斯板分享", "這是第一篇測試文章，用來確認版型正常。", ["https://picsum.photos/620/400"]),
        ("測試文章 2 - 短片測試", "這是第二篇測試文章，包含短片。", ["https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny_720p.mp4"]),
        ("測試文章 3 - risu 圖床測試", "這是第三篇測試文章，用來測試防盜鏈處理。", ["https://picsum.photos/620/401"])
    ]

    for i, (title, content, media) in enumerate(test_posts):
        media_urls = [upload_to_cloudinary(u) for u in media]
        media_urls = [u for u in media_urls if u]
        
        conn = sqlite3.connect(DB_FILE)
        conn.execute("INSERT OR REPLACE INTO posts VALUES (?,?,?,?,?,?)", 
                    (f"test_{i+1}", title, content, 9999, json.dumps(media_urls), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        print(f"✅ 已產生測試文章：{title}")

    generate_static_site()

def generate_static_site():
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT id, title, like_count, backup_time, image_urls FROM posts ORDER BY backup_time DESC").fetchall()
    conn.close()

    html = """<!DOCTYPE html><html lang="zh-TW"><head><meta charset="utf-8"><title>Dcard 西斯板備份</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>body{background:#f6f7f8;font-family:system-ui}.card{background:white;margin:15px;padding:15px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.1);}</style></head><body>
    <h1 style="text-align:center;color:#ff6b00;padding:20px;">Dcard 西斯板備份 - 最新文章</h1>"""

    for row in rows:
        post_id, title, like, time_str, imgs = row
        media = json.loads(imgs) if imgs else []
        thumb = media[0] if media else ""
        html += f'''
        <div class="card">
            <h2><a href="post_{post_id}.html">{title}</a></h2>
            <p>❤️ {like} | {time_str}</p>
            {f'<img src="{thumb}" style="max-width:220px;border-radius:8px;">' if thumb else ''}
        </div>'''
    
    html += "</body></html>"
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("📄 已產生 index.html")

if __name__ == "__main__":
    backup()
