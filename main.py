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
    
    # 第一種方式：直接上傳（最快）
    try:
        return cloudinary.uploader.upload(url, headers=headers, resource_type="auto", timeout=30)["secure_url"]
    except:
        pass
    
    # 第二種方式：先下載再上傳（針對 risu、myppt、lurl 等防盜鏈）
    try:
        import requests
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        file_obj = BytesIO(r.content)
        file_obj.name = "media.bin"
        return cloudinary.uploader.upload(file_obj, resource_type="auto", timeout=30)["secure_url"]
    except Exception as e:
        print(f"上傳失敗 {url[:80]}... : {e}")
        return None

def backup():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.goto(f"https://www.dcard.tw/f/{BOARD}", wait_until="networkidle")
        
        # 抓取最新 30 篇
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
                media: Array.from(document.querySelectorAll("img[src], video[src], video source[src]")).map(el => el.src)
            })''')
            
            title = data["title"]
            content = data["content"]
            media_urls = []
            
            for url in data["media"]:
                if url:
                    uploaded = upload_to_cloudinary(url)
                    if uploaded:
                        media_urls.append(uploaded)
            
            conn = sqlite3.connect(DB_FILE)
            conn.execute("INSERT INTO posts VALUES (?,?,?,?,?,?)", 
                        (post_id, title, content, 9999, json.dumps(media_urls), datetime.now().isoformat()))
            conn.commit()
            conn.close()
            print(f"✅ 已備份：{title}（含 {len(media_urls)} 個媒體）")
        
        browser.close()

if __name__ == "__main__":
    backup()
