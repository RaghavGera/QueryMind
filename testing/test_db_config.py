"""DatabaseConfig builds a safe libpq connection string from the DB_* variables."""

import sys
from pathlib import Path

import pytest
from psycopg.conninfo import conninfo_to_dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import DatabaseConfig


def _config(monkeypatch, **env):
    for key in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SSLMODE"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return DatabaseConfig()


def test_connection_string_round_trips(monkeypatch):
    cfg = _config(monkeypatch, DB_HOST="db.example.com", DB_PORT="6543", DB_NAME="shop", DB_USER="u", DB_PASSWORD="p")
    assert conninfo_to_dict(cfg.connection_string) == {
        "host": "db.example.com", "port": "6543", "dbname": "shop", "user": "u", "password": "p",
    }


def test_passwords_with_spaces_and_quotes_survive(monkeypatch):
    # The old f-string version split "p w" into two parameters.
    cfg = _config(monkeypatch, DB_USER="u", DB_PASSWORD="p w'd\\x=1")
    assert conninfo_to_dict(cfg.connection_string)["password"] == "p w'd\\x=1"


@pytest.mark.parametrize("value, expected", [("require", "require"), ("", None), ("  ", None)])
def test_sslmode_is_optional(monkeypatch, value, expected):
    cfg = _config(monkeypatch, DB_USER="u", DB_PASSWORD="p", DB_SSLMODE=value)
    assert conninfo_to_dict(cfg.connection_string).get("sslmode") == expected


def test_user_and_password_are_required(monkeypatch):
    with pytest.raises(ValueError):
        _config(monkeypatch, DB_USER="u")
