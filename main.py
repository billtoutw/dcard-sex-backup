import os
import json
import sqlite3
import cloudinary
import cloudinary.uploader
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from io import BytesIO
import time

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

ZENROWS_API_KEY = os.getenv("ZENROWS_API_KEY")

DB_FILE = "dcard_backup.db"
BOARD = "sex"
LIKE_THRESHOLD = 30

def zenrows_get(url, retries=2):
    """使用 ZenRows 抓取，加入重試機制"""
    payload = {
        "url": url,
        "apikey": ZENROWS_API_KEY,
        "js_render": "true",
        "antibot": "true"
    }
    for attempt in range(retries + 1):
        try:
            r = requests.get("https://api.zenrows.com/v1/", params=payload, timeout=60)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"ZenRows 嘗試 {attempt+1} 失敗: {e}")
            if attempt == retries:
                raise
            time.sleep(5)
    return ""

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
            import requests as req
            r = req.get(url, headers=headers, timeout=20)
            r.raise_for_status()
            file_obj = BytesIO(r.content)
            file_obj.name = "media.bin"
            return cloudinary.uploader.upload(file_obj, resource_type="auto", timeout=30)["secure_url"]
        except:
            return None

def backup():
    print("🔄 使用 ZenRows 抓取西斯板文章...")
    html = zenrows_get(f"https://www.dcard.tw/f/{BOARD}")
    if not html:
        print("ZenRows 抓取失敗")
        return
    
    soup = BeautifulSoup(html, "html.parser")
    
    links = soup.select('a[href*="/p/"]')
    post_ids = []
    for link in links[:30]:
        href = link.get("href", "")
        if "/p/" in href:
            post_id = href.split("/p/")[-1].split("?")[0]
            if post_id.isdigit() and post_id not in post_ids:
                post_ids.append(post_id)
    
    print(f"[DEBUG] 抓到 {len(post_ids)} 篇文章候選")

    for post_id in post_ids:
        conn = sqlite3.connect(DB_FILE)
        exists = conn.execute("SELECT id FROM posts WHERE id=?", (post_id,)).fetchone()
        conn.close()
        if exists: continue
        
        article_html = zenrows_get(f"https://www.dcard.tw/f/{BOARD}/p/{post_id}")
        if not article_html: continue
        
        article_soup = BeautifulSoup(article_html, "html.parser")
        
        title = article_soup.find("h1")
        title = title.get_text(strip=True) if title else "無標題"
        content = str(article_soup.find("main") or article_soup.body)
        
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

    generate_static_site()

def generate_static_site():
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT id, title, like_count, backup_time, image_urls FROM posts ORDER BY backup_time DESC").fetchall()
    conn.close()

    html = """<!DOCTYPE html><html lang="zh-TW"><head><meta charset="utf-8"><title>Dcard 西斯板備份</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>body{background:#f6f7f8;font-family:system-ui}.card{background:white;margin:15px;padding:15px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.1);}</style></head><body>
    <h1 style="text-align:center;color:#ff6b00;padding:20px;">Dcard 西斯板備份 - 最新文章</h1>"""

    if not rows:
        html += "<p style='text-align:center;padding:40px;color:#666;'>目前還沒有抓到文章<br>請再手動跑一次 workflow</p>"
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
