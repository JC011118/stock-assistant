import argparse
import os
import sys
import time
from datetime import datetime, timezone

# lets you run this as `python src/news_aggregator.py` from the project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import feedparser
import requests
from pymongo.errors import ServerSelectionTimeoutError

from config.config import (
    MONGO_URI, RSS_FEEDS, SCRAPE_URLS, RSS_INTERVAL, ALPHA_VANTAGE_INTERVAL, SCRAPE_INTERVAL,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ALPHA_VANTAGE_API_KEY,
)
from src.database import Database
from src.scraper import scrape_news
from src.utils import is_relevant
from src.summarizer import get_summarizer, summarize_article
from src.sentiment_analyzer import get_sentiment_model, analyze_sentiment


def fetch_rss(url):
    """Returns the feed's name and its entries."""
    # downloading with requests instead of feedparser.parse(url) because feedparser has no
    # timeout and quietly returns nothing on a 404. the user agent is because yahoo sends
    # back a 429 for python's default one
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Couldn't load {url}: {e}")
        return url, []
    feed = feedparser.parse(response.content)
    return feed.feed.get('title', url), feed.entries


def fetch_alpha_vantage():
    """Latest market news from Alpha Vantage's NEWS_SENTIMENT endpoint.

    Returns None if the key can't use this endpoint at all, so main() knows to stop asking.
    """
    params = {
        'function': 'NEWS_SENTIMENT',
        'apikey': ALPHA_VANTAGE_API_KEY,
        # one topic only, alpha vantage treats a comma separated list as "must match all of them"
        'topics': 'financial_markets',
        'limit': 10,
    }
    try:
        response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        print(f"Alpha Vantage request failed: {e}")
        return []
    if 'feed' not in data:
        # rate limits, bad keys etc. still come back as a 200, just with a message instead of news
        print(f"Alpha Vantage didn't send any news back: {data}")
        # news is premium only now, so with a free key there's no point trying again
        return None if 'premium endpoint' in str(data).lower() else []
    return data['feed']


def parse_published(article, source_type):
    """When the article came out, as a UTC datetime. None if the source doesn't say."""
    if source_type == 'rss':
        # feedparser already turns whatever date format and timezone the feed uses into a UTC time tuple
        parsed = article.get('published_parsed') or article.get('updated_parsed')
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
    elif source_type == 'alpha_vantage':
        try:
            # looks like 20250304T190107, in UTC
            return datetime.strptime(article.get('time_published', ''), '%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def normalize_article(article, source_type, source_name=''):
    """Gets RSS entries and Alpha Vantage items into the same shape so nothing else has to care where they came from."""
    # no date means we can't tell how old it is, so treat it as new. the url check stops repeats anyway
    published = parse_published(article, source_type) or datetime.now(timezone.utc)
    if source_type == 'rss':
        return {
            'title': article.get('title', ''),
            'summary': article.get('summary', article.get('description', '')),
            'publishedAt': published,
            'source': source_name or 'RSS',
            'url': article.get('link', ''),
        }
    elif source_type == 'alpha_vantage':
        return {
            'title': article.get('title', ''),
            'summary': article.get('summary', ''),
            'publishedAt': published,
            'source': article.get('source') or 'Alpha Vantage',
            'url': article.get('url', ''),
        }
    return None


def process_article(db, article, started_at):
    """Sends an alert for the article if it's new, on topic, and one we haven't seen. Returns True if it did."""
    # the feeds are full of older stories, we only care about stuff that came out after we started
    if not article['url'] or article['publishedAt'] <= started_at:
        return False
    if not is_relevant(article):
        return False
    # False here means we've already alerted on this url
    if not db.insert_article(article):
        return False

    summary = summarize_article(article)
    sentiment, impact = analyze_sentiment(article)
    notify_user(article, summary, sentiment, impact)
    return True


def notify_user(article, summary, sentiment, impact):
    message = (
        f"News: {article['title']}\n"
        f"Summary: {summary or article['title']}\n"
        f"Sentiment: {sentiment}\n"
        f"Impact: {impact}\n"
        f"Source: {article['source']}\n"
        f"URL: {article['url']}"
    )
    print(message + "\n")

    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    try:
        # plain text on purpose. telegram's markdown mode reads _ as italics, so links like
        # marketwatch's ?mod=mw_rss_topstories got mangled or the whole message got rejected
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={'chat_id': TELEGRAM_CHAT_ID, 'text': message},
            timeout=10,
        )
    except requests.RequestException as e:
        # not printing e itself, the url inside it has the bot token in it
        print(f"Couldn't reach Telegram ({type(e).__name__}), skipping this one")
        return
    if not response.ok:
        print(f"Telegram didn't take the message ({response.status_code}): {response.text}")


def main():
    parser = argparse.ArgumentParser(description="Watches financial news and sends alerts for market-moving stories.")
    parser.add_argument('--fresh', action='store_true', help="delete all saved articles before starting")
    args = parser.parse_args()

    try:
        db = Database()
    except ServerSelectionTimeoutError:
        sys.exit(f"Can't connect to MongoDB at {MONGO_URI}, is it running?")
    if args.fresh:
        db.clear()
        print("Cleared out the saved articles.")

    if not ALPHA_VANTAGE_API_KEY:
        print("No Alpha Vantage key set, sticking to RSS.")
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("Telegram isn't set up, so alerts will only show up here.")

    # load these up front so the first alert isn't stuck waiting on a download
    print("Loading models (the first run downloads about 2GB, so give it a minute)...")
    get_summarizer()
    get_sentiment_model()

    started_at = datetime.now(timezone.utc)
    last_rss = last_alpha = last_scrape = 0
    use_alpha_vantage = bool(ALPHA_VANTAGE_API_KEY)
    print("Watching for news. Ctrl+C to stop.\n")

    try:
        while True:
            now = time.time()

            if now - last_rss >= RSS_INTERVAL:
                last_rss = now
                print("Checking RSS feeds...")
                for feed_url in RSS_FEEDS:
                    source, entries = fetch_rss(feed_url)
                    for entry in entries:
                        process_article(db, normalize_article(entry, 'rss', source), started_at)

            if use_alpha_vantage and now - last_alpha >= ALPHA_VANTAGE_INTERVAL:
                last_alpha = now
                print("Checking Alpha Vantage...")
                items = fetch_alpha_vantage()
                if items is None:
                    use_alpha_vantage = False
                    print("Skipping Alpha Vantage for the rest of this run.")
                for item in items or []:
                    process_article(db, normalize_article(item, 'alpha_vantage'), started_at)

            if SCRAPE_URLS and now - last_scrape >= SCRAPE_INTERVAL:
                last_scrape = now
                print("Scraping...")
                for page_url in SCRAPE_URLS:
                    for article in scrape_news(page_url):
                        process_article(db, article, started_at)

            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
