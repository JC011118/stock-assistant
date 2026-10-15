import unittest

from src.utils import is_relevant


class TestIsRelevant(unittest.TestCase):
    def test_market_headlines(self):
        for title in [
            'Stocks rally as Fed holds rates',
            'Nvidia earnings beat estimates',
            'Treasury yields climb to a 16-year high',
            'Oil prices slump on demand worries',
        ]:
            self.assertTrue(is_relevant({'title': title}), title)

    def test_checks_the_summary_too(self):
        self.assertTrue(is_relevant({'title': 'Big day for Apple', 'summary': 'Shares jumped 8% after the event.'}))

    def test_keywords_hiding_inside_other_words_dont_count(self):
        # all of these used to get through: 'gain' is in 'again', 'company' in 'accompany', 'rise' in 'surprise'
        for title in [
            'Rain expected again this weekend',
            'Kids accompany parents to the zoo',
            'Plane makes a surprise landing',
        ]:
            self.assertFalse(is_relevant({'title': title}), title)


if __name__ == '__main__':
    unittest.main()
