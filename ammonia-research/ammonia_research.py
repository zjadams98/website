from __future__ import annotations

import html
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import feedparser

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "ammonia_news.html"

FEEDS = [
    "https://news.google.com/rss/search?q=ammonia",
    "https://news.google.com/rss/search?q=%22green+ammonia%22",
    "https://news.google.com/rss/search?q=%22blue+ammonia%22",
    "https://news.google.com/rss/search?q=%22clean+ammonia%22",
    "https://news.google.com/rss/search?q=%22ammonia+fuel%22",
    "https://news.google.com/rss/search?q=%22ammonia+shipping%22",
    "https://news.google.com/rss/search?q=%22ammonia+plant%22",
    "https://news.google.com/rss/search?q=%22ammonia+power%22",
    "https://news.google.com/rss/search?q=%22ammonia+fertilizer%22",
]

KEYWORDS = [
    "ammonia",
    "green ammonia",
    "blue ammonia",
    "clean ammonia",
    "low-carbon ammonia",
    "ammonia fuel",
    "ammonia shipping",
    "ammonia plant",
    "ammonia project",
    "ammonia export",
    "ammonia import",
    "ammonia bunker",
    "ammonia bunkering",
    "ammonia power",
    "ammonia cracking",
    "fertilizer",
]

EXCLUDE_TERMS = [
    "household",
    "cleaning product",
    "window cleaner",
    "home cleaner",
    "chemistry homework",
    "science fair",
    "classroom",
    "bleach",
    "urine",
    "aquarium",
]

MAX_AGE_DAYS = 30
MAX_ARTICLES = 60
FEATURED_COUNT = 1


def parse_published_date(entry):
    """Try to parse the article's published date into a timezone-aware datetime."""
    date_fields = [entry.get("published"), entry.get("updated")]

    for value in date_fields:
        if not value:
            continue
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass

    return None


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", text or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def normalize_title(title: str) -> str:
    clean = strip_html(title).lower()
    clean = re.sub(r"[^a-z0-9\s]", "", clean)
    return normalize_whitespace(clean)


def canonicalize_link(link: str) -> str:
    link = (link or "").strip()
    if not link:
        return ""

    parsed = urlparse(link)

    if parsed.netloc.endswith("news.google.com"):
        qs = parse_qs(parsed.query)
        if "url" in qs and qs["url"]:
            return unquote(qs["url"][0])

    return link


def infer_tags(title: str, summary: str) -> list[str]:
    text = f"{title} {summary}".lower()
    tags = []

    tag_rules = [
        ("Shipping", ["shipping", "ship", "marine", "bunkering", "bunker", "vessel", "port"]),
        ("Projects", ["project", "plant", "facility", "terminal", "announcement", "startup", "commissioning"]),
        ("Production", ["production", "electrolyzer", "synthesis", "capacity", "cracking", "fertilizer"]),
        ("Policy", ["policy", "regulation", "law", "subsidy", "mandate", "government", "minister"]),
        ("Power", ["power", "co-firing", "turbine", "generation", "utility"]),
        ("Markets", ["price", "market", "trade", "export", "import", "supply", "demand"]),
    ]

    for tag, terms in tag_rules:
        if any(term in text for term in terms):
            tags.append(tag)

    if not tags:
        tags.append("General")

    return tags[:3]


def summarize_text(title: str, summary: str, source: str) -> str:
    clean_summary = strip_html(summary)
    clean_summary = re.sub(r"\s*\[[^\]]*\]$", "", clean_summary).strip()

    if clean_summary:
        sentences = re.split(r"(?<=[.!?])\s+", clean_summary)
        kept = []
        for sentence in sentences:
            sentence = normalize_whitespace(sentence)
            if not sentence:
                continue
            if sentence.lower() == strip_html(title).lower():
                continue
            kept.append(sentence)
            if len(" ".join(kept)) > 240 or len(kept) >= 2:
                break
        summary_text = " ".join(kept).strip()
        if summary_text:
            return summary_text

    title_text = strip_html(title)
    return f"{title_text} was surfaced from {source}. Open the full article for the original reporting and additional context."


def is_relevant(title: str, summary: str = "") -> bool:
    text = f"{title} {summary}".lower()

    if not any(keyword.lower() in text for keyword in KEYWORDS):
        return False

    if any(term in text for term in EXCLUDE_TERMS):
        return False

    return True


def fetch_articles():
    """Fetch articles from all feeds, filter by relevance and age, and normalize them."""
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=MAX_AGE_DAYS)

    articles = []

    for feed_url in FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            title = strip_html(entry.get("title", "")).strip()
            raw_link = entry.get("link", "").strip()
            link = canonicalize_link(raw_link)
            raw_summary = entry.get("summary", "").strip()
            published_dt = parse_published_date(entry)

            if not title or not link or published_dt is None:
                continue

            if published_dt < cutoff:
                continue

            if not is_relevant(title, raw_summary):
                continue

            source = "Unknown"
            if hasattr(entry, "source") and isinstance(entry.source, dict):
                source = entry.source.get("title", "Unknown") or "Unknown"

            clean_summary = summarize_text(title, raw_summary, source)
            tags = infer_tags(title, clean_summary)
            hours_old = max((now_utc - published_dt).total_seconds() / 3600, 0)
            is_new = hours_old <= 24

            articles.append(
                {
                    "title": title,
                    "title_key": normalize_title(title),
                    "link": link,
                    "summary": clean_summary,
                    "published_dt": published_dt,
                    "published_display": published_dt.strftime("%Y-%m-%d %H:%M UTC"),
                    "published_short": published_dt.strftime("%b %d, %Y"),
                    "source": strip_html(source),
                    "tags": tags,
                    "is_new": is_new,
                }
            )

    return articles


def dedupe_articles(articles):
    """Remove duplicates by canonical link first, then by near-identical title."""
    seen_links = set()
    seen_titles = set()
    unique_articles = []

    for article in articles:
        link = article["link"]
        title_key = article["title_key"]

        if link in seen_links or title_key in seen_titles:
            continue

        seen_links.add(link)
        seen_titles.add(title_key)
        unique_articles.append(article)

    return unique_articles


def sort_articles_newest_first(articles):
    return sorted(articles, key=lambda x: x["published_dt"], reverse=True)


def build_article_card(article: dict, featured: bool = False) -> str:
    title = html.escape(article["title"])
    link = html.escape(article["link"], quote=True)
    source = html.escape(article["source"])
    published = html.escape(article["published_display"])
    summary = html.escape(article["summary"])
    tag_html = "".join(f'<span class="tag">{html.escape(tag)}</span>' for tag in article["tags"])
    new_badge = '<span class="new-badge">New</span>' if article["is_new"] else ""
    featured_class = " featured-card" if featured else ""

    return f"""
    <article class="news-card{featured_class}">
      <div class="card-topline">
        <div class="meta">{source} • {published}</div>
        {new_badge}
      </div>
      <a class="headline" href="{link}" target="_blank" rel="noopener noreferrer">{title}</a>
      <p class="summary">{summary}</p>
      <div class="card-footer">
        <div class="tag-row">{tag_html}</div>
        <a class="read-more" href="{link}" target="_blank" rel="noopener noreferrer">Read article</a>
      </div>
    </article>
    """


def render_html(articles):
    os.makedirs(BASE_DIR, exist_ok=True)
    run_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    new_count = sum(1 for article in articles if article["is_new"])

    featured_articles = articles[:FEATURED_COUNT]
    feed_articles = articles[FEATURED_COUNT:]

    featured_html = "".join(build_article_card(article, featured=True) for article in featured_articles)
    feed_html = "".join(build_article_card(article) for article in feed_articles)

    if not articles:
        empty_state = """
        <section class="empty-state">
          <h2>No recent ammonia articles found</h2>
          <p>No relevant ammonia-related articles were found in the last 30 days during this run.</p>
        </section>
        """
        featured_html = ""
        feed_html = empty_state

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ammonia News</title>
  <style>
    :root {{
      --bg: #f4f7fb;
      --card: #ffffff;
      --text: #111827;
      --muted: #6b7280;
      --border: #e5e7eb;
      --accent: #2563eb;
      --accent-soft: #dbeafe;
      --shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
      --radius: 18px;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      padding: 20px;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #eef4ff 0%, var(--bg) 180px);
      color: var(--text);
    }}

    .page {{
      max-width: 1050px;
      margin: 0 auto;
    }}

    .hero {{
      background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 55%, #60a5fa 100%);
      color: white;
      border-radius: 24px;
      padding: 26px 24px;
      box-shadow: var(--shadow);
      margin-bottom: 20px;
    }}

    .eyebrow {{
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      opacity: 0.85;
      margin-bottom: 10px;
    }}

    .hero h1 {{
      margin: 0 0 8px;
      font-size: clamp(28px, 4vw, 40px);
      line-height: 1.05;
    }}

    .hero p {{
      margin: 0;
      max-width: 760px;
      line-height: 1.55;
      font-size: 15px;
      opacity: 0.95;
    }}

    .status-bar {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 18px 0 20px;
    }}

    .status-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px 16px;
      box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
    }}

    .status-label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      font-weight: 700;
    }}

    .status-value {{
      font-size: 22px;
      font-weight: 800;
    }}

    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin: 0 0 18px;
    }}

    .toolbar-left h2 {{
      margin: 0 0 4px;
      font-size: 20px;
    }}

    .toolbar-left p {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}

    .search-box {{
      display: flex;
      align-items: center;
      gap: 10px;
      background: white;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 10px 14px;
      min-width: min(100%, 360px);
      box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
    }}

    .search-box input {{
      border: 0;
      outline: 0;
      width: 100%;
      font-size: 14px;
      background: transparent;
      color: var(--text);
    }}

    .featured-wrap {{
      margin-bottom: 24px;
    }}

    .section-title {{
      font-size: 18px;
      font-weight: 800;
      margin: 0 0 12px;
    }}

    .news-grid {{
      display: grid;
      gap: 16px;
    }}

    .news-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 18px 18px 16px;
      box-shadow: 0 3px 10px rgba(15, 23, 42, 0.05);
      transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
    }}

    .news-card:hover {{
      transform: translateY(-2px);
      box-shadow: var(--shadow);
      border-color: #c7d2fe;
    }}

    .featured-card {{
      padding: 22px 22px 20px;
      background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
      border-color: #bfdbfe;
    }}

    .card-topline {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }}

    .meta {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 600;
    }}

    .new-badge {{
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 800;
      padding: 4px 8px;
      border-radius: 999px;
    }}

    .headline {{
      display: inline-block;
      color: var(--text);
      font-size: 22px;
      line-height: 1.25;
      font-weight: 800;
      text-decoration: none;
      margin-bottom: 10px;
    }}

    .headline:hover {{
      color: var(--accent);
      text-decoration: underline;
    }}

    .summary {{
      margin: 0 0 14px;
      color: #334155;
      font-size: 15px;
      line-height: 1.65;
    }}

    .card-footer {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 14px;
      flex-wrap: wrap;
    }}

    .tag-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}

    .tag {{
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border-radius: 999px;
      background: #eff6ff;
      color: #1d4ed8;
      border: 1px solid #dbeafe;
      font-size: 12px;
      font-weight: 700;
    }}

    .read-more {{
      color: var(--accent);
      text-decoration: none;
      font-size: 14px;
      font-weight: 800;
      white-space: nowrap;
    }}

    .read-more:hover {{
      text-decoration: underline;
    }}

    .empty-state {{
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 28px 22px;
      text-align: center;
      color: var(--muted);
    }}

    .empty-state h2 {{
      margin: 0 0 8px;
      color: var(--text);
      font-size: 22px;
    }}

    .news-card.hidden {{
      display: none;
    }}

    @media (max-width: 680px) {{
      body {{ padding: 14px; }}
      .hero {{ padding: 22px 18px; border-radius: 20px; }}
      .headline {{ font-size: 19px; }}
      .summary {{ font-size: 14px; }}
      .card-footer {{ align-items: flex-start; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">Ammonia intelligence feed</div>
      <h1>Ammonia News</h1>
      <p>
        A live-style feed of recent ammonia-related reporting across projects, shipping, policy, power, and market developments.
        Headlines are sorted newest first and limited to the past {MAX_AGE_DAYS} days.
      </p>
    </section>

    <section class="status-bar">
      <div class="status-card">
        <div class="status-label">Last updated</div>
        <div class="status-value">{html.escape(run_time)}</div>
      </div>
      <div class="status-card">
        <div class="status-label">Articles shown</div>
        <div class="status-value">{len(articles)}</div>
      </div>
      <div class="status-card">
        <div class="status-label">Published in last 24h</div>
        <div class="status-value">{new_count}</div>
      </div>
    </section>

    <section class="toolbar">
      <div class="toolbar-left">
        <h2>Recent coverage</h2>
        <p>Search headlines or summaries and click any story to open the original article.</p>
      </div>
      <label class="search-box" aria-label="Search ammonia news">
        <span>🔎</span>
        <input id="newsSearch" type="text" placeholder="Search ammonia stories..." />
      </label>
    </section>

    <section class="featured-wrap">
      <h2 class="section-title">Featured story</h2>
      <div class="news-grid">
        {featured_html}
      </div>
    </section>

    <section>
      <h2 class="section-title">News feed</h2>
      <div id="newsFeed" class="news-grid">
        {feed_html}
      </div>
    </section>
  </main>

  <script>
    (function () {{
      const input = document.getElementById('newsSearch');
      const cards = Array.from(document.querySelectorAll('.news-card'));
      if (!input) return;

      input.addEventListener('input', () => {{
        const q = input.value.trim().toLowerCase();
        cards.forEach((card) => {{
          const text = card.innerText.toLowerCase();
          card.classList.toggle('hidden', q && !text.includes(q));
        }});
      }});
    }})();
  </script>
</body>
</html>
"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_doc)


def main():
    articles = fetch_articles()
    articles = dedupe_articles(articles)
    articles = sort_articles_newest_first(articles)
    articles = articles[:MAX_ARTICLES]
    render_html(articles)

    print(f"Wrote {len(articles)} articles to:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()
