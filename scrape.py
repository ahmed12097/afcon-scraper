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

# ✅ التحقق من وجود مكتبة التخفي وتثبيتها تلقائياً إذا نقصت
try:
    from selenium_stealth import stealth
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "selenium-stealth"])
    from selenium_stealth import stealth

# =========================
# ✅ إعدادات المتصفح المخفي (للبور بي آي وجيت هب)
# =========================
def get_stealth_driver():
    options = Options()
    options.add_argument("--headless=new") # تشغيل خفي لعدم تعطيل Power BI
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # إخفاء هوية الأتمتة
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # إضافة User-Agent حقيقي
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # ✅ تطبيق تقنية Stealth لإخفاء بصمة Selenium تماماً
    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True)
    return driver

# =========================
# ✅ دوال المساعدة (Cleaning)
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
# ✅ التنفيذ الرئيسي (Main Logic)
# =========================
SCHEDULE_URL = "https://fbref.com/en/comps/656/schedule/"
driver = get_stealth_driver()

try:
    print("🚀 جاري محاولة الوصول للموقع...")
    driver.get(SCHEDULE_URL)
    
    # الانتظار الذكي لظهور الجدول
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.stats_table")))
    
    # محاكاة حركة بشرية بسيطة (تصفح)
    driver.execute_script("window.scrollBy(0, 500);")
    time.sleep(random.uniform(2, 4))
    
    html_main = driver.page_source
    print("✅ تم سحب البيانات بنجاح!")
finally:
    driver.quit()

# تحويل HTML إلى DataFrame
tables = pd.read_html(StringIO(html_main))
raw_df = tables[0].copy()

# ✅ 1. جدول المباريات (afcon_2025_matches)
raw_df = raw_df.dropna(subset=["Date", "Home", "Away"]).copy()
raw_df["HomeTeam"] = raw_df["Home"].apply(clean_team_name)
raw_df["AwayTeam"] = raw_df["Away"].apply(clean_team_name)
raw_df["Date"] = pd.to_datetime(raw_df["Date"], errors="coerce")

# فصل النتائج
raw_df["Score"] = raw_df["Score"].astype(str)
score_split = raw_df["Score"].str.split("–", expand=True)
if score_split.shape[1] >= 2:
    raw_df["HomeGoals"] = pd.to_numeric(score_split[0], errors="coerce")
    raw_df["AwayGoals"] = pd.to_numeric(score_split[1], errors="coerce")
else:
    raw_df["HomeGoals"], raw_df["AwayGoals"] = None, None

raw_df["MatchStatus"] = raw_df["HomeGoals"].apply(lambda x: "Played" if pd.notna(x) else "Upcoming")
raw_df["MatchID"] = raw_df["Date"].astype(str).str[:10] + "_" + raw_df["HomeTeam"].str.replace(" ", "")

# استخراج الروابط
match_links = get_match_report_links(html_main)
raw_df["MatchReportLink"] = None
played_idx = raw_df[raw_df["MatchStatus"] == "Played"].index.tolist()
for idx, link in zip(played_idx, match_links):
    raw_df.loc[idx, "MatchReportLink"] = link

# الجداول النهائية التي ستظهر في Power BI Navigator:
afcon_2025_matches = raw_df[["MatchID", "Date", "Time", "MatchStatus", "HomeTeam", "AwayTeam", "HomeGoals", "AwayGoals", "Score", "Venue", "Referee", "MatchReportLink"]].copy()

# ✅ 2. تلخيص الفرق (teams_summary)
teams_summary = (afcon_2025_matches.groupby("HomeTeam").agg(PlayedMatches=("MatchID", "count")).reset_index())

# ملاحظة لـ Power BI: سيظهر لك جداول afcon_2025_matches و teams_summary في القائمة.
