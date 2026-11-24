import Passwords


def test_hash_round_trip():
    stored = Passwords.hash_password("s3cret!")
    assert stored != "s3cret!"
    assert Passwords.is_hashed(stored)
    assert Passwords.verify(stored, "s3cret!")
    assert not Passwords.verify(stored, "wrong")


def test_hashes_are_salted():
    assert Passwords.hash_password("same") != Passwords.hash_password("same")


def test_hash_fits_the_widened_column():
    assert len(Passwords.hash_password("x" * 100)) <= 255


def test_legacy_plain_text_still_verifies():
    assert not Passwords.is_hashed("1")
    assert Passwords.verify("1", "1")
    assert not Passwords.verify("1", "2")


def test_empty_stored_password_never_matches():
    assert not Passwords.verify(None, "")
    assert not Passwords.verify("", "")
