from app.services.openalex import abstract_from_index


def test_abstract_from_index_orders_words():
    assert abstract_from_index({"world": [1], "hello": [0]}) == "hello world"


def test_abstract_from_index_empty():
    assert abstract_from_index(None) is None
    assert abstract_from_index({}) is None
