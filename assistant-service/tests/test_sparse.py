"""Golden tests for the sparse encoding (SPEC v1).

The expected indices below pin the exact encoding. The identical test lives
in collector-service: both copies must produce byte-identical vectors.
"""
from app.sparse import (
    SPEC_VERSION,
    VOCAB_MOD,
    SparseVector,
    encode_sparse,
    sparse_dot,
    token_index,
    tokenize,
)


def test_spec_version_pinned():
    assert SPEC_VERSION == 1
    assert VOCAB_MOD == 1 << 16


def test_golden_vector():
    vector = encode_sparse("Джазовый концерт на Немиге вечером")
    assert vector is not None
    assert vector.indices == [24432, 41485, 58058, 63153]
    assert vector.values == [1.0, 1.0, 1.0, 1.0]


def test_tokenize_drops_stopwords_and_short_tokens():
    assert tokenize("и в на концерт") == ["концерт"]
    assert tokenize("я") == []


def test_normalization_is_case_and_yo_insensitive():
    assert tokenize("Немига") == tokenize("немига")
    assert token_index("немига") == token_index("немига".replace("и", "и"))


def test_empty_or_stopwords_only_gives_none():
    assert encode_sparse(None) is None
    assert encode_sparse("") is None
    assert encode_sparse("и в на") is None
    assert not SparseVector()


def test_deterministic_and_sorted():
    first = encode_sparse("джаз джаз рок")
    second = encode_sparse("джаз джаз рок")
    assert first is not None and second is not None
    assert first.indices == second.indices == sorted(first.indices)
    assert all(0 <= i < VOCAB_MOD for i in first.indices)
    by_token = dict(zip(first.indices, first.values))
    jazz = token_index("джаз")
    assert by_token[jazz] == 2.0


def test_sparse_dot_scores_overlap_only():
    query = encode_sparse("джаз концерт")
    same = encode_sparse("джаз концерт")
    other = encode_sparse("опера балет")
    assert query is not None and same is not None and other is not None
    assert sparse_dot(query, same) > 0
    assert sparse_dot(query, other) == 0.0
