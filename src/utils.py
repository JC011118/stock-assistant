import re

# words that usually mean a story is about markets or the economy. they only match at the
# start of a word, so 'rate' still catches 'rates' but 'gain' doesn't fire on 'again'
KEYWORDS = [
    'stock', 'market', 'economy', 'economic', 'finance', 'financial', 'invest',
    'earnings', 'shares', 'profit', 'revenue', 'guidance', 'trade', 'trading',
    'selloff', 'sell-off', 'bulls', 'bears', 'index', 'fund', 'crash', 'tariff', 'bond',
    'yield', 'exchange', 'equities', 'sale', 'buyout', 'acquisition', 'merger', 'ipo', 'bank',
    'decline', 'rise', 'slump', 'rebound', 'loss', 'gain', 'value', 'currency',
    'supply', 'production', 'industry', 'company', 'price', 'cost', 'output',
    'ratings', 'downgrade', 'upgrade', 'manufacturing', 'crypto',
    'reserve', 'fed', 'rate', 'inflation', 'recession', 'trump',
]

KEYWORD_PATTERN = re.compile(r'\b(?:' + '|'.join(re.escape(k) for k in KEYWORDS) + ')')


def is_relevant(article):
    """True if the title or summary mentions anything market related."""
    text = f"{article.get('title') or ''} {article.get('summary') or ''}".lower()
    return KEYWORD_PATTERN.search(text) is not None
