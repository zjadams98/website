import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser

OUTPUT_FILE = r"C:\Users\zjada\OneDrive\Desktop\Coding\new_ammonia_links.txt"

FEEDS = [
    "https://news.google.com/rss/search?q=ammonia",
    "https://news.google.com/rss/search?q=%22green+ammonia%22",
    "https://news.google.com/rss/search?q=%22blue+ammonia%22",
    "https://news.google.com/rss/search?q=%22clean+ammonia%22",
    "https://news.google.com/rss/search?q=%22ammonia+fuel%22",
    "https://news.google.com/rss/search?q=%22ammonia+shipping%22",
    "https://news.google.com/rss/search?q=%22ammonia+plant%22",
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
    "ammonia power",
]

MAX_AGE_DAYS = 30


def parse_published_date(entry):
    """
    Try to parse the article's published date into a timezone-aware datetime.
    Returns None if unavailable or unparseable.
    """
    date_fields = [
        entry.get("published"),
        entry.get("updated"),
    ]

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


def is_relevant(title, summary=""):
    text = f"{title} {summary}".lower()
    return any(keyword.lower() in text for keyword in KEYWORDS)


def fetch_articles():
    """
    Fetch articles from all feeds, filter by relevance and age,
    and return normalized article dictionaries.
    """
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=MAX_AGE_DAYS)

    articles = []

    for feed_url in FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", "").strip()
            published_dt = parse_published_date(entry)

            if not title or not link:
                continue

            if not is_relevant(title, summary):
                continue

            if published_dt is None:
                continue

            if published_dt < cutoff:
                continue

            source = "Unknown"
            if hasattr(entry, "source") and isinstance(entry.source, dict):
                source = entry.source.get("title", "Unknown")

            articles.append(
                {
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published_dt": published_dt,
                    "published_display": published_dt.strftime("%Y-%m-%d %H:%M UTC"),
                    "source": source,
                }
            )

    return articles


def dedupe_articles(articles):
    """
    Remove duplicate links.
    """
    seen_links = set()
    unique_articles = []

    for article in articles:
        link = article["link"]
        if link in seen_links:
            continue
        seen_links.add(link)
        unique_articles.append(article)

    return unique_articles


def sort_articles_newest_first(articles):
    return sorted(articles, key=lambda x: x["published_dt"], reverse=True)


def write_output_file(articles):
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    run_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"Ammonia-related articles found in the last {MAX_AGE_DAYS} days\n")
        f.write(f"Generated: {run_time}\n")
        f.write(f"Sorted: newest published date first\n")
        f.write("\n")

        if not articles:
            f.write("No relevant ammonia-related articles found.\n")
            return

        for i, article in enumerate(articles, start=1):
            f.write(f"{i}. {article['title']}\n")
            f.write(f"   Published: {article['published_display']}\n")
            f.write(f"   Source: {article['source']}\n")
            f.write(f"   Link: {article['link']}\n")
            f.write("\n")


def main():
    articles = fetch_articles()
    articles = dedupe_articles(articles)
    articles = sort_articles_newest_first(articles)
    write_output_file(articles)

    print(f"Wrote {len(articles)} articles to:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()