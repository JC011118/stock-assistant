from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def scrape_news(url):
    """Pulls headlines off a news site's page.

    Every site's HTML is different so each one needs its own parsing below. Reuters is the
    only one so far, and these days it answers scrapers with a 401, so treat it as an example.
    """
    try:
        # lots of sites refuse python's default user agent
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Couldn't scrape {url}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    articles = []
    if 'reuters.com' in url:
        for item in soup.select('article'):
            title_tag = item.find('h2')
            link_tag = item.find('a', href=True)
            if not (title_tag and link_tag):
                continue
            articles.append({
                'title': title_tag.get_text(strip=True),
                'summary': '',  # listing pages don't have one
                'publishedAt': datetime.now(timezone.utc),  # no timestamp on the page, so use when we saw it
                'source': 'Reuters',
                'url': urljoin(url, link_tag['href']),
            })
    return articles
