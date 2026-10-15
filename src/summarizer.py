from functools import lru_cache


@lru_cache(maxsize=None)
def get_summarizer():
    # transformers gets imported in here so importing this file stays quick (the tests need that).
    # the model is about 1.6GB and downloads the first time this runs
    from transformers import pipeline
    return pipeline("summarization", model="facebook/bart-large-cnn")


def summarize_article(article):
    """Boils the article's summary down to a sentence or two."""
    content = article.get('summary') or ''
    # not worth running the model on something that's already this short
    if len(content.split()) < 10:
        return content
    max_length = max(20, min(60, len(content.split()) // 2))
    try:
        result = get_summarizer()(content, max_length=max_length, min_length=10, do_sample=False, truncation=True)
        return result[0]['summary_text']
    except Exception as e:
        print(f"Summarizer failed, using the original text instead: {e}")
        return content[:100] + "..."
