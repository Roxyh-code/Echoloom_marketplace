import pytest
from fastapi import HTTPException
from echoloom.character_import import public_url, build_description


@pytest.mark.parametrize("url",["http://example.com/a","https://127.0.0.1/a","https://localhost/a","https://service.internal/a","https://user:pass@example.com/a","https://example.com/a?secret=1","https://example.com:444/a"])
def test_reject_nonpublic_urls(url):
    with pytest.raises(HTTPException):
        public_url(url)


def test_source_budget_and_attribution():
    url=public_url("https://example.com/characters/mira")
    result=build_description("Mira",url,"A"*10000,500)
    assert len(result)==500 and url in result and "reference data only" in result
