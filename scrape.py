import os
import re
import time
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


# =========================
# ✅ SETTINGS
# =========================
SCHEDULE_URL = "https://fbref.com/en/comps/656/schedule/"

# ✅ Works on GitHub Actions / Linux
OUTPUT_DIR = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

MATCHES_FILE = os.path.join(OUTPUT_DIR, "afcon_2025_matches.csv")
GOALS_FILE   = os.path.join(OUTPUT_DIR, "afcon_2025_goals.csv")
TEAMS_FILE   = os.path.join(OUTPUT_DIR, "teams_summary.csv")
PLAYERS_FILE = os.path.join(OUTPUT_DIR, "players_summary.csv")
MATCHES_SUMMARY_FILE = os.path.join(OUTPUT_DIR, "matches_summary.csv")


# =========================
# ✅ HELPERS
# =========================
def clean_team_name(name):
    name = str(name).strip()
    name = re.sub(r"^[a-z]{2}\s+", "", name)      # remove prefix code
    name = re.sub(r"\s+[a-z]{2}$", "", name)      # remove suffix code
    return name.strip()


def save_debug_html(html_text):
    """Save debug HTML for inspection in GitHub Actions artifacts."""
    try:
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(html_text if html_text else "EMPTY HTML")
    except Exception as e:
        print("⚠️ Could not write debug_page.html:", repr(e))


def get_html_selenium_strong(url, wait=25, retries=2):
    """
    Strong Selenium fetch for GitHub Actions:
    - waits for schedule table: table#sched_all
    - adds UA + removes webdriver flag
    - retries if table not found
    - saves debug_page.html on failure
    """
    last_error = None

    for attempt in range(retries + 1):
        driver = None
        try:
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")

            # ✅ Anti-bot basics
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)

            # ✅ Remove webdriver flag
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            driver.get(url)

            # ✅ Wait for schedule table
            WebDriverWait(driver, wait).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table#sched_all"))
            )

            # Scroll
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

            html = driver.page_source

            # ✅ Cloudflare detection
            if "Just a moment" in html or "cf-browser-verification" in html or "Cloudflare" in html:
                save_debug_html(html)
                raise Exception("Cloudflare detected in HTML")

            driver.quit()
            return html

        except Exception as e:
            last_error = e
            print(f"⚠️ Selenium attempt {attempt+1}/{retries+1} failed: {repr(e)}")

            if driver:
                try:
                    html_debug = driver.page_source
                    print("----- HTML DEBUG START -----")
                    print(html_debug[:1200])
                    print("----- HTML DEBUG END -----")
                    save_debug_html(html_debug)
                except Exception as ee:
                    print("⚠️ Could not capture debug HTML:", repr(ee))
                    save_debug_html("FAILED TO CAPTURE HTML")

                try:
                    driver.quit()
                except:
                    pass

            time.sleep(2)

    raise Exception(f"❌ Failed to load page after retries. Last error: {repr(last_error)}")


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


def extract_goals_global(html, home_team, away_team):
    soup = BeautifulSoup(html, "html.parser")
    goals = []

    goal_icons = soup.select("div.event_icon.goal")

    for icon in goal_icons:
        parent = icon.parent
        text = parent.get_text(" ", strip=True)

        a = parent.find("a")
        scorer = a.get_text(strip=True) if a else text.split("·")[0].strip()

        minute_match = re.search(r"·\s*(\d+\+?\d*)[’']", text)
        minute = minute_match.group(1) if minute_match else None

        event_container = parent.find_parent("div", class_="event")
        team_scored = None

        if event_container and event_container.get("id"):
            event_id = event_container.get("id").lower()
            if event_id == "a":
                team_scored = home_team
            elif event_id == "b":
                team_scored = away_team

        if team_scored is None:
            team_scored = "Unknown"

        if scorer and minute:
            goals.append({
                "TeamScored": team_scored,
                "Scorer": scorer,
                "Minute": minute,
                "GoalType": "Goal",
                "Raw": text
            })

    return goals


# =========================
# ✅ MAIN
# =========================
def main():
    # Ensure debug file always exists (prevents artifact issues)
    save_debug_html("DEBUG START\n")

    print("✅ Task 1: Fetch schedule HTML...")
    html = get_html_selenium_strong(SCHEDULE_URL, wait=25, retries=2)

    # Extra check
    if "Just a moment" in html or "cf-browser-verification" in html or "Cloudflare" in html:
        print("⚠️ Cloudflare page detected!")
        save_debug_html(html)
        raise Exception("Blocked by Cloudflare")

    print("✅ Task 2: Read matches table...")
    tables = pd.read_html(StringIO(html))

    if not tables:
        print("❌ No tables extracted from HTML.")
        save_debug_html(html)
        raise ValueError("No tables found in schedule page")

    matches_df = tables[0].copy()
    print("✅ matches rows:", len(matches_df))

    # Clean core
    matches_df = matches_df.dropna(subset=["Date", "Home", "Away"]).copy()
    matches_df["HomeTeam"] = matches_df["Home"].apply(clean_team_name)
    matches_df["AwayTeam"] = matches_df["Away"].apply(clean_team_name)

    matches_df["Date"] = pd.to_datetime(matches_df["Date"], errors="coerce")

    matches_df["Score"] = matches_df["Score"].astype(str)
    score_split = matches_df["Score"].str.split("–", expand=True)

    matches_df["HomeGoals"] = pd.to_numeric(score_split[0], errors="coerce")
    matches_df["AwayGoals"] = pd.to_numeric(score_split[1], errors="coerce")

    matches_df["MatchStatus"] = matches_df["HomeGoals"].apply(
        lambda x: "Played" if pd.notna(x) else "Upcoming"
    )

    matches_df["MatchID"] = (
        matches_df["Date"].astype(str).str[:10] + "_" +
        matches_df["HomeTeam"].str.replace(" ", "") + "_vs_" +
        matches_df["AwayTeam"].str.replace(" ", "")
    )

    # Match report links
    print("✅ Task 3: Extract Match Report links...")
    match_links = get_match_report_links(html)
    matches_df["MatchReportLink"] = None

    played_idx = matches_df[matches_df["MatchStatus"] == "Played"].index.tolist()
    for i, link in zip(played_idx, match_links):
        matches_df.loc[i, "MatchReportLink"] = link

    # Final matches file
    matches_clean = matches_df[[
        "MatchID", "Date", "Time", "MatchStatus",
        "HomeTeam", "AwayTeam",
        "HomeGoals", "AwayGoals", "Score",
        "Venue", "Referee",
        "MatchReportLink"
    ]].copy()

    matches_clean.to_csv(MATCHES_FILE, index=False, encoding="utf-8-sig")
    print("✅ Saved matches file:", MATCHES_FILE)

    # =========================
    # GOALS SCRAPE
    # =========================
    print("✅ Task 4: Scrape goals from played match reports...")
    matches_reports = matches_clean[matches_clean["MatchReportLink"].notna()].copy()
    print("✅ matches with reports:", len(matches_reports))

    all_goals = []

    for _, row in matches_reports.iterrows():
        link = row["MatchReportLink"]

        try:
            html_match = get_html_selenium_strong(link, wait=25, retries=1)
            goals = extract_goals_global(html_match, row["HomeTeam"], row["AwayTeam"])

            for g in goals:
                all_goals.append({
                    "MatchID": row["MatchID"],
                    "Date": row["Date"],
                    "HomeTeam": row["HomeTeam"],
                    "AwayTeam": row["AwayTeam"],
                    "TeamScored": g["TeamScored"],
                    "Scorer": g["Scorer"],
                    "Minute": g["Minute"],
                    "GoalType": g["GoalType"],
                    "ReportLink": link
                })

        except Exception as e:
            print("⚠️ Error on match:", row["MatchID"], str(e))

        time.sleep(1)

    goals_df = pd.DataFrame(all_goals)
    goals_df.to_csv(GOALS_FILE, index=False, encoding="utf-8-sig")
    print("✅ Saved goals file:", GOALS_FILE)
    print("✅ goals_df:", goals_df.shape)

    # =========================
    # SUMMARIES
    # =========================
    print("✅ Task 5: Build summaries...")

    if goals_df.empty:
        print("⚠️ goals_df is empty. Summaries will be empty too.")

    teams_summary = (
        goals_df.groupby("TeamScored")
        .agg(GoalsScored=("TeamScored", "count"), MatchesWithGoals=("MatchID", "nunique"))
        .reset_index()
        .sort_values("GoalsScored", ascending=False)
    ) if not goals_df.empty else pd.DataFrame(columns=["TeamScored", "GoalsScored", "MatchesWithGoals"])

    teams_summary.to_csv(TEAMS_FILE, index=False, encoding="utf-8-sig")
    print("✅ Saved teams summary:", TEAMS_FILE)

    players_summary = (
        goals_df.groupby("Scorer")
        .agg(Goals=("Scorer", "count"), MatchesScoredIn=("MatchID", "nunique"))
        .reset_index()
        .sort_values("Goals", ascending=False)
    ) if not goals_df.empty else pd.DataFrame(columns=["Scorer", "Goals", "MatchesScoredIn"])

    players_summary.to_csv(PLAYERS_FILE, index=False, encoding="utf-8-sig")
    print("✅ Saved players summary:", PLAYERS_FILE)

    match_total_goals = (
        goals_df.groupby(["MatchID", "Date", "HomeTeam", "AwayTeam"])
        .size()
        .reset_index(name="TotalGoals")
    ) if not goals_df.empty else pd.DataFrame(columns=["MatchID", "Date", "HomeTeam", "AwayTeam", "TotalGoals"])

    match_total_goals.to_csv(MATCHES_SUMMARY_FILE, index=False, encoding="utf-8-sig")
    print("✅ Saved matches summary:", MATCHES_SUMMARY_FILE)

    print("✅ DONE ✅ All files updated successfully!")


if __name__ == "__main__":
    main()
