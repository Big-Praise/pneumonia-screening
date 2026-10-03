import pytest
from sqlalchemy import inspect, select

import auth
import config
import db


def test_tables_created():
    assert {"users", "patients", "scans"} <= set(inspect(db._engine).get_table_names())


def test_register_stores_bcrypt_hash_not_plaintext():
    auth.register_user("dr.ade", "s3cure-pass", "Dr Ade")
    with db.get_session() as s:
        row = s.scalar(select(db.User).where(db.User.username == "dr.ade"))
    assert row.password_hash != "s3cure-pass"
    assert "s3cure-pass" not in row.password_hash
    assert row.password_hash.startswith("$2b$")  # bcrypt identifier


def test_login_success_and_failure():
    auth.register_user("dr.ade", "s3cure-pass")
    assert auth.authenticate("dr.ade", "s3cure-pass").username == "dr.ade"
    assert auth.authenticate("DR.ADE ", "s3cure-pass") is not None  # normalised
    assert auth.authenticate("dr.ade", "wrong-pass") is None
    assert auth.authenticate("nobody", "s3cure-pass") is None


def test_duplicate_username_rejected():
    auth.register_user("dr.ade", "s3cure-pass")
    with pytest.raises(auth.AuthError, match="taken"):
        auth.register_user("Dr.Ade", "another-pass")


@pytest.mark.parametrize("username,password", [
    ("ab", "s3cure-pass"),          # username too short
    ("bad name", "s3cure-pass"),    # space not allowed
    ("dr.ade", "short"),            # password too short
    ("dr.ade", "x" * 73),           # beyond bcrypt's 72-byte limit
])
def test_invalid_input_rejected(username, password):
    with pytest.raises(auth.AuthError):
        auth.register_user(username, password)


def test_registration_code_enforced(monkeypatch):
    monkeypatch.setattr(config, "REGISTRATION_CODE", "letmein")
    with pytest.raises(auth.AuthError, match="registration code"):
        auth.register_user("dr.ade", "s3cure-pass", registration_code="nope")
    assert auth.register_user("dr.ade", "s3cure-pass", registration_code="letmein")


def test_auth_user_carries_no_hash():
    user = auth.register_user("dr.ade", "s3cure-pass")
    assert not any("hash" in f for f in user.__dataclass_fields__)
