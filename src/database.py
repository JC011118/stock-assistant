from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from config.config import MONGO_URI, DB_NAME, COLLECTION_NAME


class Database:
    def __init__(self, db_name=DB_NAME, collection_name=COLLECTION_NAME):
        # give up after 5s if mongo isn't running instead of pymongo's default 30
        self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        # the url is how we tell articles apart, so make it unique (also makes the lookup fast)
        self.collection.create_index('url', unique=True)

    def insert_article(self, article):
        """Saves the article. Returns False if we already have one with the same URL."""
        try:
            self.collection.insert_one(article)
            return True
        except DuplicateKeyError:
            return False

    def get_recent_articles(self, limit=10):
        """Newest articles first."""
        return list(self.collection.find().sort('publishedAt', -1).limit(limit))

    def clear(self):
        """Deletes every saved article."""
        self.collection.delete_many({})

    def close(self):
        self.client.close()
