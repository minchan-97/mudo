"""Explicitly non-neural baseline until the user's trained NM is supplied."""
import math
import re
from collections import Counter

TOKEN = re.compile(r"[가-힣A-Za-z0-9]{2,}")


class MarkovBoundary:
    def __init__(self, examples):
        self.pairs = Counter()
        self.starts = Counter()
        self.vocab = set()
        self.examples = 0
        for text in examples:
            words = TOKEN.findall(str(text).lower())
            if len(words) < 3:
                continue
            self.examples += 1
            self.vocab.update(words)
            self.pairs.update(zip(words,words[1:]))
            self.starts.update(words[:-1])

    def score(self, text):
        words = TOKEN.findall(str(text).lower())
        if self.examples < 3 or len(words) < 3:
            return None
        # Mean negative log probability mapped to 0..1 for soft ranking.
        # Unknown words remain possible through additive smoothing.
        v = max(2,len(self.vocab))
        nll = -sum(math.log((self.pairs[a,b]+1)/(self.starts[a]+v))
                   for a,b in zip(words,words[1:]))/(len(words)-1)
        return round(1/(1+math.exp(min(30,max(-30,nll-4)))),4)
