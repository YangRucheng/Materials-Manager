from app.services.common import split_or_search_terms


def test_split_or_search_terms_normalizes_delimiters_and_empty_items() -> None:
    assert split_or_search_terms(" 断路器||接触器｜断路器| ") == ("断路器", "接触器")
    assert split_or_search_terms(None) == ()
    assert split_or_search_terms("｜ |") == ()
