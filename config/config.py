import os

from dotenv import load_dotenv

# keys and tokens live in a .env file in the project root (copy .env.example)
# so they never end up on github
load_dotenv()

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME = 'news_database'
COLLECTION_NAME = 'articles'

RSS_FEEDS = [
    'https://feeds.bloomberg.com/markets/news.rss',
    'https://feeds.content.dowjones.io/public/rss/mw_topstories',  # MarketWatch top stories
    'https://feeds.content.dowjones.io/public/rss/mw_bulletins',  # MarketWatch breaking news
    'https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US',  # Yahoo Finance, S&P 500 news
]

# pages to scrape headlines from. each site needs its own parser in scraper.py
SCRAPE_URLS = []

# how often to check each source, in seconds
RSS_INTERVAL = 60
SCRAPE_INTERVAL = 60
# alpha vantage made their news endpoint premium only, so this source needs a paid key.
# with a free key you just get a "premium endpoint" message back and the bot stops asking
ALPHA_VANTAGE_INTERVAL = 60

# all optional. no telegram = alerts just print in the terminal, no alpha vantage = rss only
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', '')
