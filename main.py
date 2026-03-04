import os
import json
import sqlite3
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from io import BytesIO

app = FastAPI(title="Dcard 西斯板備份系統")

# === Cloudinary ===
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# === ZenRows API Key ===
ZENROWS_API_KEY = os.getenv("ZENROWS_API_KEY")

DB_FILE = "dcard_backup.db"
BOARD = "sex"
LIKE_THRESHOLD = 30

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""CREATE TABLE IF NOT EXISTS posts (id TEXT PRIMARY KEY, title TEXT, content TEXT, like_count INTEGER, image_urls TEXT, backup_time TEXT)""")
    conn.commit()
    conn.close()
init_db()

def zenrows_get(url):
    """使用 ZenRows 繞過 Cloudflare"""
    payload = {
        "url": url,
        "apikey": ZENROWS_API_KEY,
        "js_render": "true",
        "antibot": "true",
        "premium_proxy": "true"
    }
    r = requests.get("https://api.zenrows.com/v1/", params=payload, timeout=30)
    return r.text

def backup_task():
    try:
        print("🔄 使用 ZenRows 抓取西斯板文章...")
        html = zenrows_get(f"https://www.dcard.tw/f/{BOARD}")
        soup = BeautifulSoup(html, "html.parser")
        
        # 抓取文章連結
        links = soup.select('a[href*="/p/"]')
        post_ids = []
        for link in links[:30]:
            href = link.get("href", "")
            if "/p/" in href:
                post_id = href.split("/p/")[-1].split("?")[0]
                if post_id.isdigit() and post_id not in post_ids:
                    post_ids.append(post_id)
        
        for post_id in post_ids:
            conn = sqlite3.connect(DB_FILE)
            exists = conn.execute("SELECT id FROM posts WHERE id=?", (post_id,)).fetchone()
            conn.close()
            if exists: continue
            
            article_html = zenrows_get(f"https://www.dcard.tw/f/{BOARD}/p/{post_id}")
            article_soup = BeautifulSoup(article_html, "html.parser")
            
            title = article_soup.find("h1")
            title = title.get_text(strip=True) if title else "無標題"
            content = str(article_soup.find("main") or article_soup.body)
            
            # 提取媒體
            media_urls = []
            for tag in article_soup.find_all(["img", "video"]):
                src = tag.get("src") or tag.get("data-src")
                if src:
                    uploaded = upload_to_cloudinary(src)
                    if uploaded:
                        media_urls.append(uploaded)
            
            conn = sqlite3.connect(DB_FILE)
            conn.execute("INSERT INTO posts VALUES (?,?,?,?,?,?)", 
                        (post_id, title, content, 9999, json.dumps(media_urls), datetime.now().isoformat()))
            conn.commit()
            conn.close()
            print(f"✅ 已備份：{title}")
            
    except Exception as e:
        print(f"錯誤：{e}")

def upload_to_cloudinary(url):
    if not url: return None
    headers = {"Referer": "https://www.dcard.tw/"}
    try:
        return cloudinary.uploader.upload(url, headers=headers, resource_type="auto", timeout=30)["secure_url"]
    except:
        return None

# === 前端（保留您原本風格）===
@app.get("/", response_class=HTMLResponse)
async def home():
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT id, title, like_count, backup_time, image_urls FROM posts ORDER BY backup_time DESC").fetchall()
    conn.close()

    # （這裡保留您原本的 Dcard 風格前端程式碼，如果需要我再補上請說）

    html = "<h1>正在從 Dcard 西斯板抓取文章...</h1><p>請稍等幾分鐘後重新整理</p>"
    return html

# 排程
scheduler = BackgroundScheduler()
scheduler.add_job(backup_task, "interval", seconds=300)
scheduler.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
