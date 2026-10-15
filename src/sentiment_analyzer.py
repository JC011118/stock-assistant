from functools import lru_cache


@lru_cache(maxsize=None)
def get_sentiment_model():
    # FinBERT is trained on financial text, so it gets stuff like "beat estimates" way better
    # than a generic sentiment model. ~440MB download the first time
    from transformers import pipeline
    return pipeline("sentiment-analysis", model="yiyanghkust/finbert-tone")


def analyze_sentiment(article):
    """Runs FinBERT on the article and turns the result into a rough guess at the market impact."""
    # a lot of feed items come with an empty summary, the headline is still worth scoring
    text = article.get('summary') or article.get('title') or ''
    if not text:
        return "Neutral", "No significant impact predicted"

    try:
        # truncation so a long article can't blow past BERT's 512 token limit and crash the loop
        result = get_sentiment_model()(text, truncation=True)[0]
    except Exception as e:
        print(f"FinBERT failed on this one: {e}")
        return "Unknown", "No significant impact predicted"

    label = result['label'].lower()
    score = result['score']
    # only call a direction when the model is fairly sure
    if label == 'positive' and score > 0.7:
        impact = "Potential stock market increase"
    elif label == 'negative' and score > 0.7:
        impact = "Potential stock market decrease"
    else:
        impact = "No significant impact predicted"

    return label.capitalize(), impact
