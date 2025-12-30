import os
import re
import time
import random
from io import StringIO
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ✅ إضافة مكتبة التخفي (يجب إضافتها في requirements.txt)
try:
    from selenium_stealth import stealth
except ImportError:
    os.system('pip install selenium-stealth')
    from selenium_stealth import stealth

# =========================
# ✅ SETTINGS
# =========================
SCHEDULE_URL = "https://fbref.com/en/comps/656/schedule/"
OUTPUT_DIR = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =========================
# ✅ HELPERS
# =========================
def clean_team_name(name):
    name = str(name).strip()
    name = re.sub(r"^[a-z]{2}\s+", "", name)
    name = re.sub(r"\s+[a-z]{2}$", "", name)
    return name.strip()

def get_html_selenium_strong(url, wait=30):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    # محاكاة لغات المتصفح
    options.add_argument("--lang=en-US,en;q=0.9")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # ✅ تطبيق تقنية Stealth لإخفاء بصمة Selenium
    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )

    try:
        # إضفاء لمسة عشوائية قبل الدخول
        time.sleep(random.uniform(2, 5))
        driver.get(url)
        
        # الانتظار الذكي للجدول
        WebDriverWait(driver, wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.stats_table"))
        )
        
        # تمرير بطيء لمحاكاة البشر
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(random.uniform(1, 3))
        
        html = driver.page_source
        return html
    except Exception as e:
        print(f"⚠️ Error: {str(e)}")
        return driver.page_source
    finally:
        driver.quit()

# =========================
# ✅ MAIN
# =========================
def main():
    print("🚀 Starting AFCON Scraper with Stealth Mode...")
    html = get_html_selenium_strong(SCHEDULE_URL)

    if "Just a moment" in html or "Cloudflare" in html:
        print("❌ Blocked by Cloudflare despite Stealth mode. GitHub Actions IPs are likely blacklisted.")
        return

    # استكمال باقي الكود الخاص بك هنا (تحويل الجداول وحفظ الـ CSV)
    # ... (باقي كود التنظيف والحفظ كما هو في النسخة السابقة)
    
    print("✅ Process Completed!")

if __name__ == "__main__":
    main()
