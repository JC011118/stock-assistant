# Stock News Assistant

A Python bot that watches financial news feeds and pings you on Telegram when something market related comes out. Each alert comes with a short summary from BART and a sentiment read from FinBERT, a BERT model trained on financial text.

## How it works

Every minute it pulls the latest headlines from a few RSS feeds (Bloomberg Markets, MarketWatch, Yahoo Finance). For each story it:

1. skips anything published before the bot started, so you don't get a flood of old news on launch
2. checks the headline and summary against a keyword list to make sure it's actually about markets
3. saves it to MongoDB, using the URL to skip stories it has already alerted on
4. summarizes it with `facebook/bart-large-cnn`
5. scores the sentiment with `yiyanghkust/finbert-tone`, and if the model is more than 70% sure it's positive or negative, flags a possible move up or down
6. prints the alert and sends it to Telegram

Alpha Vantage's news API can be added as a second source if you have a premium key, and there's a basic scraper for sites that don't have RSS.

An alert looks something like this:

```
News: Treasury yields jump as traders pare back rate-cut bets
Summary: Ten-year yields hit their highest level in a month after stronger than expected jobs data.
Sentiment: Negative
Impact: Potential stock market decrease
Source: Bloomberg Markets
URL: https://www.bloomberg.com/news/articles/...
```

## Setup

You'll need Python 3.8 or newer and MongoDB running locally.

```bash
# MongoDB on a Mac (or with Docker: docker run -d -p 27017:27017 mongo)
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community

pip install -r requirements.txt   # torch is the big one
cp .env.example .env
```

Then fill in `.env`. Everything in it is optional:

- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`: message [@BotFather](https://t.me/BotFather) on Telegram to make a bot and it'll give you the token. Send your new bot any message, then open `https://api.telegram.org/bot<your token>/getUpdates` and grab the number under `"chat": {"id": ...}`. If you leave these blank, alerts just print in the terminal.
- `ALPHA_VANTAGE_API_KEY`: their news endpoint is premium only now. A free key gets a "premium endpoint" reply, and the bot skips Alpha Vantage for the rest of that run.
- `MONGO_URI`: only needed if Mongo isn't at `mongodb://localhost:27017/`.

`.env` is in `.gitignore`, so your keys stay off GitHub.

## Running it

From the project root:

```bash
python src/news_aggregator.py
```

The first run downloads the two models (about 2GB total) before it starts watching. After that it checks the feeds every minute until you hit Ctrl+C.

Saved articles stick around between runs, so restarting won't send you anything twice. To wipe them and start clean:

```bash
python src/news_aggregator.py --fresh
```

## Changing what it watches

Feeds and polling intervals are in `config/config.py`. Any RSS feed works, just add its URL to `RSS_FEEDS`.

What counts as market news is decided by the `KEYWORDS` list in `src/utils.py`. Keywords only match at the start of a word, so `rate` catches "rates" but not "corporate".

For sites without RSS, put the page URL in `SCRAPE_URLS` and write a parser for that site in `src/scraper.py`. The Reuters one in there is mostly an example at this point, since Reuters answers scrapers with a 401. Check a site's terms before you scrape it.

## Tests

```bash
python -m unittest
```

The database tests use a separate `news_database_test` database and get skipped if Mongo isn't running. The rest don't need Mongo, the models, or an internet connection.

## Project layout

```
config/config.py            feeds, intervals, loads keys from .env
src/news_aggregator.py      main loop: fetch, filter, dedupe, summarize, score, alert
src/database.py             MongoDB wrapper (dedupes on URL)
src/utils.py                keyword filter
src/summarizer.py           BART summaries
src/sentiment_analyzer.py   FinBERT sentiment and the impact guess
src/scraper.py              HTML scraping for sites without RSS
tests/                      unit tests
```

## Heads up

- The "impact" line is just FinBERT's label when it's confident. It isn't a price prediction and definitely isn't financial advice.
- The keyword filter is pretty simple. The default feeds are all finance already, so mostly it just keeps out the odd off-topic story.
- RSS feeds move around or die every so often. If one breaks you'll see a `Couldn't load ...` line in the output.
