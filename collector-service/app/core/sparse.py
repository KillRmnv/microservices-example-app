"""Sparse text vectors for Qdrant Hybrid search (SPEC v1).

KEEP IN SYNC with ``assistant-service/app/sparse.py``: index-time and
query-time encodings must be byte-identical, otherwise sparse scores are
garbage. The golden test in ``tests/test_sparse.py`` pins the encoding in
both services.

Method: lowercase + ``ё→е`` normalization, regex tokenization, stopword
removal, hashing-trick indices (md5 mod 2**16), raw term-frequency values.
No model download, no heavy dependencies. Russian morphology (lemmatization)
is deliberately out of scope for v1 — dense vectors cover inflections.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field

SPEC_VERSION = 1
SPARSE_VECTOR_NAME = "text-sparse"
VOCAB_MOD = 1 << 16
MIN_TOKEN_LEN = 2

TOKEN_RE = re.compile(r"[a-zа-яё0-9]+")

STOPWORDS = frozenset("""
и в на с к о по из у а но для это как что все от до же ли бы не ни со во об обо
при без над под между через или если когда где там здесь вот так его ее их мы
вы они она оно я ты он меня тебя себя нас вас них него нее этот эта эти того
этого который которая которое которые мой моя мое мои твой твоя твое твои наш
наша наше наши ваш ваша ваше ваши сам сама само сами весь вся всё каждый каждая
каждое каждые другой другая другое другие такой такая такое такие тут туда сюда
потом затем сейчас теперь уже еще только лишь даже ведь ну да нет конечно
пожалуйста спасибо привет добрый день вечер утро
the a an and or of to in on for with at by from is are was were be been being
have has had do does did will would can could should may might must shall this
that these those i you he she it we they me him her us them my your his its our
their what which who whom where when how why not no yes if then else so than
too very just about into over after before between through as
""".split())


@dataclass
class SparseVector:
    indices: list[int] = field(default_factory=list)
    values: list[float] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.indices)


def normalize_token(token: str) -> str:
    return token.casefold().replace("ё", "е")


def tokenize(text: str) -> list[str]:
    """Content tokens: normalized, stopwords and short tokens removed."""
    tokens = []
    for raw in TOKEN_RE.findall(text.casefold()):
        token = normalize_token(raw)
        if len(token) >= MIN_TOKEN_LEN and token not in STOPWORDS:
            tokens.append(token)
    return tokens


def token_index(token: str) -> int:
    digest = hashlib.md5(token.encode("utf-8")).hexdigest()
    return int(digest, 16) % VOCAB_MOD


def encode_sparse(text: str | None) -> SparseVector | None:
    """TF-weighted sparse vector, or None when no content tokens remain."""
    if not text:
        return None
    counts: dict[int, int] = {}
    for token in tokenize(text):
        index = token_index(token)
        counts[index] = counts.get(index, 0) + 1
    if not counts:
        return None
    indices = sorted(counts)
    return SparseVector(
        indices=indices,
        values=[float(counts[i]) for i in indices],
    )


def sparse_dot(query: SparseVector, doc: SparseVector) -> float:
    """Dot product over shared indices (brute-force scoring for tests)."""
    doc_values = dict(zip(doc.indices, doc.values))
    return math.fsum(value * doc_values.get(index, 0.0)
                     for index, value in zip(query.indices, query.values))
