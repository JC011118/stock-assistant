import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import feedparser

from src.news_aggregator import fetch_alpha_vantage, normalize_article, process_article

# cut down version of a real feed. the -0500 offset is on purpose, the old hand-rolled
# date parsing fell over on numeric timezones
SAMPLE_FEED = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Stocks slide as Treasury yields jump</title>
      <link>https://example.com/stocks-slide?mod=mw_rss_topstories</link>
      <description>The S&amp;P 500 fell 1.2% after a hot inflation reading.</description>
      <pubDate>Tue, 04 Mar 2025 09:30:00 -0500</pubDate>
    </item>
  </channel>
</rss>"""

STARTED_AT = datetime(2025, 3, 4, 12, 0, tzinfo=timezone.utc)


def make_article(**changes):
    article = {
        'title': 'Nasdaq slides into correction territory',
        'summary': 'Tech stocks kept falling on Tuesday.',
        'publishedAt': STARTED_AT + timedelta(minutes=5),
        'source': 'Test',
        'url': 'https://example.com/nasdaq',
    }
    article.update(changes)
    return article


class FakeDatabase:
    """Just enough of Database to remember which urls it's seen."""

    def __init__(self):
        self.urls = set()

    def insert_article(self, article):
        if article['url'] in self.urls:
            return False
        self.urls.add(article['url'])
        return True


class TestNormalizeArticle(unittest.TestCase):
    def test_rss_entry(self):
        entry = feedparser.parse(SAMPLE_FEED).entries[0]
        article = normalize_article(entry, 'rss', 'Test Feed')
        self.assertEqual(article['title'], 'Stocks slide as Treasury yields jump')
        self.assertEqual(article['source'], 'Test Feed')
        self.assertEqual(article['url'], 'https://example.com/stocks-slide?mod=mw_rss_topstories')
        # 9:30 in New York is 14:30 UTC
        self.assertEqual(article['publishedAt'], datetime(2025, 3, 4, 14, 30, tzinfo=timezone.utc))

    def test_alpha_vantage_item(self):
        item = {
            'title': 'Fed holds rates steady',
            'summary': 'The Federal Reserve left rates unchanged.',
            'time_published': '20250304T190107',
            'source': 'Benzinga',
            'url': 'https://example.com/fed',
        }
        article = normalize_article(item, 'alpha_vantage')
        self.assertEqual(article['source'], 'Benzinga')
        self.assertEqual(article['publishedAt'], datetime(2025, 3, 4, 19, 1, 7, tzinfo=timezone.utc))

    def test_missing_date_counts_as_new(self):
        article = normalize_article({'title': 'No date on this one', 'link': 'https://example.com/x'}, 'rss')
        self.assertLess(datetime.now(timezone.utc) - article['publishedAt'], timedelta(seconds=5))


# the models and telegram are swapped out so these run instantly and don't send anything
@patch('src.news_aggregator.notify_user')
@patch('src.news_aggregator.analyze_sentiment', return_value=('Negative', 'Potential stock market decrease'))
@patch('src.news_aggregator.summarize_article', return_value='Tech stocks fell again.')
class TestProcessArticle(unittest.TestCase):
    def test_new_article_gets_one_alert(self, summarize, sentiment, notify):
        db = FakeDatabase()
        self.assertTrue(process_article(db, make_article(), STARTED_AT))
        self.assertFalse(process_article(db, make_article(), STARTED_AT))  # same story on the next poll
        notify.assert_called_once()

    def test_skips_stories_from_before_we_started(self, summarize, sentiment, notify):
        old = make_article(publishedAt=STARTED_AT - timedelta(hours=1))
        self.assertFalse(process_article(FakeDatabase(), old, STARTED_AT))
        notify.assert_not_called()

    def test_skips_off_topic_stories(self, summarize, sentiment, notify):
        weather = make_article(title='Rain again this weekend', summary='Bring an umbrella.')
        self.assertFalse(process_article(FakeDatabase(), weather, STARTED_AT))
        notify.assert_not_called()

    def test_skips_stories_without_a_link(self, summarize, sentiment, notify):
        self.assertFalse(process_article(FakeDatabase(), make_article(url=''), STARTED_AT))
        notify.assert_not_called()


def fake_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    return response


@patch('builtins.print')  # keeps alpha vantage's messages out of the test output
@patch('src.news_aggregator.requests.get')
class TestFetchAlphaVantage(unittest.TestCase):
    def test_returns_the_feed(self, get, _print):
        get.return_value = fake_response({'feed': [{'title': 'Fed holds rates steady'}]})
        self.assertEqual(fetch_alpha_vantage(), [{'title': 'Fed holds rates steady'}])

    def test_free_key_on_the_premium_endpoint_means_stop(self, get, _print):
        # the actual reply you get with a free key now
        get.return_value = fake_response({'Information': (
            'Thank you for using Alpha Vantage! This is a premium endpoint. You may subscribe to any of the '
            'premium plans at https://www.alphavantage.co/premium/ to instantly unlock all premium endpoints'
        )})
        self.assertIsNone(fetch_alpha_vantage())

    def test_other_messages_just_mean_no_news_this_time(self, get, _print):
        get.return_value = fake_response({'Information': (
            'Our standard API rate limit is 25 requests per day. Please subscribe to any of the premium plans '
            'at https://www.alphavantage.co/premium/ to instantly remove all daily rate limits.'
        )})
        self.assertEqual(fetch_alpha_vantage(), [])


if __name__ == '__main__':
    unittest.main()
