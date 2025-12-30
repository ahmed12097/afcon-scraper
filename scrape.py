import os
import re
import time
import random
import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ✅ تثبيت وتفعيل مكتبة التخفي لتجاوز الكابتشا
try:
    from selenium_stealth import stealth
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "selenium-stealth"])
    from selenium_stealth import stealth

# =========================
# ✅ إعداد المتصفح بأقصى درجات التخفي
# =========================
def get_advanced_stealth_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # إخفاء هوية الأتمتة تماماً
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # محاكاة متصفح حقيقي
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # تطبيق Stealth لمحاكاة المعايير البشرية (لغات، كرت الشاشة، المنصة)
    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True)
    return driver

# =========================
# ✅ دوال المعالجة والتنظيف
# =========================
def clean_team_name(name):
    name = str(name).strip()
    name = re.sub(r"^[a-z]{2}\s+", "", name)
    name = re.sub(r"\s+[a-z]{2}$", "", name)
    return name.strip()

def get_match_report_links(html):
    soup = BeautifulSoup(html, "html.parser")
    match_links = []
    rows = soup.select("table.stats_table tbody tr")
    for r in rows:
        report_cell = r.find("td", {"data-stat": "match_report"})
        if report_cell and report_cell.find("a"):
            link = "https://fbref.com" + report_cell.find("a")["href"]
            match_links.append(link)
    return match_links

# =========================
# ✅ العمليات الرئيسية
# =========================
URL = "https://fbref.com/en/comps/656/schedule/"
driver = get_advanced_stealth_driver()

try:
    print("🚀 جاري محاولة الوصول للموقع...")
    driver.get(URL)
    
    # انتظار ذكي لظهور جدول المواعيد
    WebDriverWait(driver, 40).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.stats_table")))
    
    # محاكاة تصفح بشري بالتمرير العشوائي
    driver.execute_script("window.scrollBy(0, 400);")
    time.sleep(random.uniform(3, 6))
    
    html_content = driver.page_source
    print("✅ تم سحب البيانات بنجاح!")
finally:
    driver.quit()

# تحويل البيانات إلى جداول
tables = pd.read_html(StringIO(html_content))
matches_raw = tables[0].copy()

# ✅ معالجة جدول المباريات الأساسي
matches_raw = matches_raw.dropna(subset=["Date", "Home", "Away"]).copy()
matches_raw["HomeTeam"] = matches_raw["Home"].apply(clean_team_name)
matches_raw["AwayTeam"] = matches_raw["Away"].apply(clean_team_name)
matches_raw["Date"] = pd.to_datetime(matches_raw["Date"], errors="coerce")

# تحليل النتائج والأهداف
matches_raw["Score"] = matches_raw["Score"].astype(str)
score_parts = matches_raw["Score"].str.split("–", expand=True)
if score_parts.shape[1] >= 2:
    matches_raw["HomeGoals"] = pd.to_numeric(score_parts[0], errors="coerce")
    matches_raw["AwayGoals"] = pd.to_numeric(score_parts[1], errors="coerce")
else:
    matches_raw["HomeGoals"], matches_raw["AwayGoals"] = None, None

matches_raw["MatchStatus"] = matches_raw["HomeGoals"].apply(lambda x: "Played" if pd.notna(x) else "Upcoming")

# استخراج روابط التقارير للمباريات الملعوبة
links = get_match_report_links(html_content)
matches_raw["MatchReportLink"] = None
played_rows = matches_raw[matches_raw["MatchStatus"] == "Played"].index.tolist()
for i, l in zip(played_rows, links):
    matches_raw.loc[i, "MatchReportLink"] = l

# الجداول النهائية التي ستظهر في Power BI
afcon_2025_matches = matches_raw[["Date", "Time", "MatchStatus", "HomeTeam", "AwayTeam", "HomeGoals", "AwayGoals", "Score", "Venue", "Referee", "MatchReportLink"]].copy()

teams_summary = afcon_2025_matches.groupby("HomeTeam").size().reset_index(name="MatchesCount")

# ✅ أمر الحفظ النهائي (لجيت هب وللجهاز)
OUTPUT_DIR = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)
afcon_2025_matches.to_csv(os.path.join(OUTPUT_DIR, "afcon_2025_matches.csv"), index=False, encoding="utf-8-sig")
