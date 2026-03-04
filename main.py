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
LIKE_THRESHOLD = 10   # 降低門檻，讓更容易抓到文章

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
    print("🔄 [DEBUG] 開始抓取 Dcard 西斯板文章...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"https://www.dcard.tw/f/{BOARD}", wait_until="networkidle")
        print(f"[DEBUG] 已進入看板: {BOARD}")
        
        posts = page.evaluate('''() => {
            return Array.from(document.querySelectorAll('a[href*="/p/"]')).slice(0, 30).map(a => {
                const m = a.href.match(/p\\/(\\d+)/);
                return m ? {id: m[1]} : null;
            }).filter(Boolean);
        }''')
        print(f"[DEBUG] 抓到 {len(posts)} 篇文章候選")

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
            media_urls = [upload_to_cloudinary(u) for u in data["media"] if u]
            media_urls = [u for u in media_urls if u]
            
            conn = sqlite3.connect(DB_FILE)
            conn.execute("INSERT OR REPLACE INTO posts VALUES (?,?,?,?,?,?)", 
                        (post_id, title, content, 9999, json.dumps(media_urls), datetime.now().isoformat()))
            conn.commit()
            conn.close()
            print(f"✅ 已備份真實文章：{title} (ID: {post_id})")

        browser.close()

    generate_static_site()

def generate_static_site():
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT id, title, like_count, backup_time, image_urls FROM posts ORDER BY backup_time DESC").fetchall()
    conn.close()
    print(f"[DEBUG] 資料庫共有 {len(rows)} 篇文章")

    html = """<!DOCTYPE html><html lang="zh-TW"><head><meta charset="utf-8"><title>Dcard 西斯板備份</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>body{background:#f6f7f8;font-family:system-ui}.card{background:white;margin:15px;padding:15px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.1);}</style></head><body>
    <h1 style="text-align:center;color:#ff6b00;padding:20px;">Dcard 西斯板備份 - 最新文章</h1>"""

    if not rows:
        html += "<p style='text-align:center;padding:40px;color:#666;'>目前還沒有抓到文章<br>請再跑一次 workflow</p>"
    else:
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
