#!/usr/bin/env python3
"""personal-dashboard data fetcher.
Runs in GitHub Actions to collect data from multiple sources,
writes JSON files into site/data/ for the static dashboard.
"""

import json
import os
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site", "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_json(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [WARN] {url} -> {e}")
        return None

def fetch_text(url, timeout=15):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode()
    except Exception as e:
        print(f"  [WARN] {url} -> {e}")
        return None

def safe_write(filename, data):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [OK] {filename} ({len(json.dumps(data))} bytes)")


# ── Weather (wttr.in) ────────────────────────────────────────────────
def fetch_weather():
    print("[Weather] Fetching Chongqing weather...")
    raw = fetch_json("https://wttr.in/Chongqing?format=j1")
    if not raw:
        safe_write("weather.json", {"error": True, "updated_at": datetime.now(CST).isoformat()})
        return

    cc = raw.get("current_condition", [{}])[0]
    result = {
        "temperature": cc.get("temp_C"),
        "feels_like": cc.get("FeelsLikeC"),
        "condition": cc.get("weatherDesc", [{}])[0].get("value", ""),
        "humidity": cc.get("humidity"),
        "wind": f'{cc.get("windspeedKmph", "?")} km/h',
        "wind_dir": cc.get("winddir16Point", ""),
        "visibility": cc.get("visibility", ""),
        "location": "Chongqing",
        "updated_at": datetime.now(CST).isoformat(),
    }
    safe_write("weather.json", result)


# ── GitHub ───────────────────────────────────────────────────────────
def fetch_github():
    print("[GitHub] Fetching user repos...")
    token = os.environ.get("INPUT_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    username = os.environ.get("INPUT_GH_USER") or os.environ.get("GH_USER") or "Jacken-Wu"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # fetch user profile
    user_data = fetch_json(f"https://api.github.com/users/{username}", headers)
    if not user_data:
        safe_write("github.json", {"error": True, "updated_at": datetime.now(CST).isoformat()})
        return

    # fetch repos (sorted by push date, top 10)
    repos = fetch_json(
        f"https://api.github.com/users/{username}/repos?sort=pushed&per_page=10&direction=desc",
        headers
    ) or []

    repo_list = []
    total_stars = 0
    for r in repos:
        repo_list.append({
            "name": r.get("name", "?"),
            "description": r.get("description") or "",
            "language": r.get("language") or "",
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "updated_at": r.get("pushed_at", "")[:10] if r.get("pushed_at") else "",
            "url": r.get("html_url", ""),
        })
        total_stars += r.get("stargazers_count", 0)

    # Fetch all starred repos (paginate up to 100)
    starred_all = []
    page = 1
    max_starred = 100
    while len(starred_all) < max_starred:
        starred_page = fetch_json(
            f"https://api.github.com/users/{username}/starred?per_page=100&page={page}",
            headers
        )
        if not starred_page or len(starred_page) == 0:
            break
        starred_all.extend(starred_page)
        page += 1
    print(f"  Found {len(starred_all)} starred repos total")
    starred = starred_all[:max_starred]

    starred_list = []
    for r in starred:
        starred_list.append({
            "name": r.get("name", "?"),
            "owner": r.get("owner", {}).get("login", ""),
            "description": r.get("description") or "",
            "language": r.get("language") or "",
            "stars": r.get("stargazers_count", 0),
            "updated_at": r.get("pushed_at", "")[:10] if r.get("pushed_at") else "",
            "url": r.get("html_url", ""),
            "latest_release": "",
        })

    # Fetch latest release date for each starred repo (parallel)
    print(f"  Fetching release dates for {len(starred_list)} starred repos (parallel, 10 workers)...")

    def fetch_release(idx, repo):
        owner = repo["owner"]
        name = repo["name"]
        if not owner or not name:
            return idx, ""
        release_url = f"https://api.github.com/repos/{owner}/{name}/releases/latest"
        release_data = fetch_json(release_url, headers)
        if release_data and "published_at" in release_data:
            return idx, release_data["published_at"][:10]
        return idx, ""

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_release, i, repo): i for i, repo in enumerate(starred_list)}
        for future in as_completed(futures):
            idx, release_date = future.result()
            starred_list[idx]["latest_release"] = release_date
            r = starred_list[idx]
            print(f"    {r['owner']}/{r['name']}: {release_date or 'no release'}")

    result = {
        "username": username,
        "avatar_url": user_data.get("avatar_url", ""),
        "public_repos": user_data.get("public_repos", 0),
        "followers": user_data.get("followers", 0),
        "following": user_data.get("following", 0),
        "total_stars": total_stars,
        "repos": repo_list,
        "starred_repos": starred_list,
        "updated_at": datetime.now(CST).isoformat(),
    }
    safe_write("github.json", result)


# ── arXiv ────────────────────────────────────────────────────────────
def fetch_arxiv():
    print("[arXiv] Fetching category RSS feeds...")

    headers = {"User-Agent": "PersonalDashboard/1.0"}
    # 相关分类的 RSS 订阅
    categories = ["cs.SY", "cs.MA", "cs.RO", "cs.LG", "eess.SY"]
    keywords = [
        "bus", "bunching", "transit",
        "mpc", "model predictive",
        "connected vehicle", "cav", "v2x",
        "mixed traffic", "autonomous",
        "marl", "multi-agent", "reinforcement",
        "safety critical", "safe control",
        "vehicle infrastructure", "platoon",
        "traffic signal", "tube",
    ]

    all_papers = []
    seen_ids = set()

    for cat in categories:
        url = f"https://rss.arxiv.org/rss/{cat}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                xml_text = resp.read().decode()
        except Exception as e:
            print(f"  [WARN] {cat} -> {e}")
            continue

        try:
            root = ET.fromstring(xml_text)
            # RSS: channel → item[]
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for item in root.findall(".//item"):
                title = item.findtext("title", "").replace("\n", " ").strip()
                link = item.findtext("link", "")
                desc = item.findtext("description", "")
                pub_date = item.findtext("pubDate", "")[:10]

                # 提取 arxiv ID
                paper_id = link.split("/")[-1].split("v")[0] if link else ""
                if not paper_id or paper_id in seen_ids:
                    continue

                # 关键词过滤
                text_lower = (title + " " + desc).lower()
                if not any(kw in text_lower for kw in keywords):
                    continue

                seen_ids.add(paper_id)
                # 清理 title（arXiv RSS 标题以 "Title: " 开头）
                clean_title = title.replace("Title: ", "", 1).strip()

                # 从 description 里提取作者
                author_match = __import__("re").search(r"Authors?: (.+?)(?:\n|&lt|$)", desc)
                authors = author_match.group(1).strip() if author_match else ""
                if authors:
                    author_list = [a.strip().split()[-1] for a in authors.split(",")[:3] if a.strip()]
                    author_str = ", ".join(author_list) if author_list else ""
                    if len(authors.split(",")) > 3:
                        author_str += " et al."
                else:
                    author_str = ""

                all_papers.append({
                    "id": paper_id,
                    "title": clean_title[:200],
                    "authors": author_str,
                    "published": pub_date,
                    "link": link,
                    "summary": "",
                })

        except ET.ParseError as e:
            print(f"  [WARN] {cat} XML parse error: {e}")
            continue

    all_papers.sort(key=lambda p: p["published"], reverse=True)
    result = {"papers": all_papers[:10], "updated_at": datetime.now(CST).isoformat()}
    safe_write("arxiv.json", result)
    print(f"  [OK] {len(all_papers[:10])} papers matched from {len(categories)} categories")


# ── Daily (quote + bird) ──────────────────────────────────────────────
def fetch_daily():
    print("[Daily] Generating daily content...")
    now = datetime.now(CST)
    day_of_year = now.timetuple().tm_yday

    quotes = [
        ("The best way to predict the future is to invent it.", "Alan Kay"),
        ("Science is a way of thinking much more than it is a body of knowledge.", "Carl Sagan"),
        ("The only impossible journey is the one you never begin.", "Tony Robbins"),
        ("Control is not about eliminating uncertainty, but learning to navigate it.", "Unknown"),
        ("A good system is one you can trust even when you're not watching it.", "Unknown"),
        ("In the middle of difficulty lies opportunity.", "Albert Einstein"),
        ("The purpose of abstraction is not to be vague, but to create a new semantic level.", "Edsger Dijkstra"),
        ("Simplicity is prerequisite for reliability.", "Edsger Dijkstra"),
        ("Debugging is twice as hard as writing the code in the first place.", "Brian Kernighan"),
        ("Every expert was once a beginner.", "Unknown"),
        ("The map is not the territory.", "Alfred Korzybski"),
        ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
        ("A person who never made a mistake never tried anything new.", "Albert Einstein"),
        ("We are what we repeatedly do. Excellence, then, is not an act, but a habit.", "Aristotle"),
        ("The reasonable man adapts himself to the world; the unreasonable one persists in trying to adapt the world to himself.", "George Bernard Shaw"),
        ("In the long run, the sharpest weapon of all is a kind and gentle spirit.", "Anne Frank"),
        ("Look deep into nature, and then you will understand everything better.", "Albert Einstein"),
        ("To raise new questions, new possibilities, to regard old problems from a new angle, requires creative imagination.", "Albert Einstein"),
        ("A theory can be proved by experiment; but no path leads from experiment to the birth of a theory.", "Albert Einstein"),
        ("If you can't explain it simply, you don't understand it well enough.", "Albert Einstein"),
        ("The important thing is not to stop questioning.", "Albert Einstein"),
        ("A system must be as simple as possible, but no simpler.", "Unknown"),
        ("Feedback is the breakfast of champions.", "Ken Blanchard"),
        ("The most dangerous phrase in the language is: 'We've always done it this way.'", "Grace Hopper"),
        ("Premature optimization is the root of all evil.", "Donald Knuth"),
        ("Talk is cheap. Show me the code.", "Linus Torvalds"),
        ("Any sufficiently advanced technology is indistinguishable from magic.", "Arthur C. Clarke"),
        ("Technology is a useful servant but a dangerous master.", "Christian Lous Lange"),
        ("First solve the problem, then write the code.", "John Johnson"),
        ("Make it work, make it right, make it fast.", "Kent Beck"),
    ]

    idx = day_of_year % len(quotes)
    quote_text, quote_author = quotes[idx]

    # bird list — common Chongqing species
    birds = [
        ("Great Tit", "大山雀"),
        ("Light-vented Bulbul", "白头鹎"),
        ("Spotted Dove", "珠颈斑鸠"),
        ("Eurasian Magpie", "喜鹊"),
        ("Azure-winged Magpie", "灰喜鹊"),
        ("Yellow-browed Warbler", "黄眉柳莺"),
        ("Common Kingfisher", "普通翠鸟"),
        ("White Wagtail", "白鹡鸰"),
        ("Crested Myna", "八哥"),
        ("Collared Finchbill", "领雀嘴鹎"),
        ("Red-billed Starling", "丝光椋鸟"),
        ("Blue Magpie", "红嘴蓝鹊"),
        ("Long-tailed Shrike", "棕背伯劳"),
        ("Oriental Turtle Dove", "山斑鸠"),
        ("Black Drongo", "黑卷尾"),
    ]
    bird_idx = day_of_year % len(birds)
    bird_en, bird_cn = birds[bird_idx]

    result = {
        "quote": {"text": quote_text, "author": quote_author},
        "bird": {"name_en": bird_en, "name_cn": bird_cn},
        "day_of_year": day_of_year,
        "date": now.strftime("%Y-%m-%d"),
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()],
        "updated_at": now.isoformat(),
    }
    safe_write("daily.json", result)


# ── Timestamp ────────────────────────────────────────────────────────
def write_timestamp():
    now = datetime.now(CST)
    result = {
        "updated_at": now.isoformat(),
        "timestamp": int(now.timestamp()),
    }
    safe_write("timestamp.json", result)


# ── Main ─────────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  Personal Dashboard — Data Fetcher")
    print(f"  Started at {datetime.now(CST).isoformat()}")
    print("=" * 50)

    steps = [
        ("Weather", fetch_weather),
        ("GitHub", fetch_github),
        ("arXiv", fetch_arxiv),
        ("Daily", fetch_daily),
        ("Timestamp", write_timestamp),
    ]

    exit_code = 0
    for name, func in steps:
        print(f"\n── [{name}] ──")
        try:
            func()
        except Exception as e:
            print(f"  [ERROR] {name} failed: {e}")
            safe_write(f"{name.lower().split()[0]}.json", {"error": True, "message": str(e), "updated_at": datetime.now(CST).isoformat()})
            exit_code = 1

    print(f"\n{'=' * 50}")
    print(f"  Done. Files written to {OUTPUT_DIR}")
    print(f"{'=' * 50}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
