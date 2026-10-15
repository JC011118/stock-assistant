import unittest
from datetime import datetime, timezone

from pymongo.errors import ServerSelectionTimeoutError

from src.database import Database

# separate db so running the tests never touches the real articles
TEST_DB_NAME = 'news_database_test'


def make_article(url='http://test.com', published=datetime(2025, 3, 4, tzinfo=timezone.utc)):
    return {
        'title': 'Test Article',
        'summary': 'This is a test',
        'publishedAt': published,
        'source': 'Test',
        'url': url,
    }


class TestDatabase(unittest.TestCase):
    def setUp(self):
        try:
            self.db = Database(db_name=TEST_DB_NAME)
        except ServerSelectionTimeoutError:
            self.skipTest("MongoDB isn't running")

    def tearDown(self):
        self.db.client.drop_database(TEST_DB_NAME)
        self.db.close()

    def test_insert_article(self):
        self.assertTrue(self.db.insert_article(make_article()))
        self.assertFalse(self.db.insert_article(make_article()))  # same url, should get skipped

    def test_recent_articles_are_newest_first(self):
        self.db.insert_article(make_article('http://test.com/old', datetime(2025, 3, 3, tzinfo=timezone.utc)))
        self.db.insert_article(make_article('http://test.com/new', datetime(2025, 3, 4, tzinfo=timezone.utc)))
        urls = [a['url'] for a in self.db.get_recent_articles()]
        self.assertEqual(urls, ['http://test.com/new', 'http://test.com/old'])


if __name__ == '__main__':
    unittest.main()
