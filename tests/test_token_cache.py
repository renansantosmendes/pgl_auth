from pgl_auth.token_cache import TokenCache


def test_saved_token_is_loaded_for_the_same_account(tmp_path):
    cache = TokenCache(tmp_path / "token.json")

    cache.save("20210001", "tok", 3600)

    assert cache.load("20210001") == "tok"


def test_token_of_another_account_is_not_returned(tmp_path):
    cache = TokenCache(tmp_path / "token.json")
    cache.save("20210001", "tok", 3600)

    assert cache.load("20219999") is None


def test_expired_token_is_not_returned(tmp_path):
    cache = TokenCache(tmp_path / "token.json")
    cache.save("20210001", "tok", 30)

    assert cache.load("20210001") is None


def test_missing_or_corrupt_file_returns_none(tmp_path):
    path = tmp_path / "token.json"
    cache = TokenCache(path)
    assert cache.load("20210001") is None

    path.write_text("{ not json", encoding="utf-8")
    assert cache.load("20210001") is None


def test_clear_removes_the_file_and_is_idempotent(tmp_path):
    cache = TokenCache(tmp_path / "token.json")
    cache.save("20210001", "tok", 3600)

    cache.clear()
    cache.clear()

    assert not (tmp_path / "token.json").exists()


def test_save_creates_missing_folders(tmp_path):
    cache = TokenCache(tmp_path / "nested" / "dir" / "token.json")

    cache.save("20210001", "tok", 3600)

    assert cache.load("20210001") == "tok"
