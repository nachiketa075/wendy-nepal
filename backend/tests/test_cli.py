"""F-01 regression for the admin command line: errors must not print stored values."""

import sys

import pytest
from sqlalchemy.exc import OperationalError

from app import cli
from app.models import Account

from .conftest import PASSWORD, make_account

EMAIL = "zephyrine.quillfeather@example.com"
NAME = "Zephyrine Quillfeather"
SENSITIVE = (EMAIL, "zephyrine", "Zephyrine", "Quillfeather", PASSWORD, "$argon2")


def _run(monkeypatch, capsys, *argv: str) -> tuple[int | str | None, str]:
    """Run the CLI as a command; return its exit status and everything it printed."""
    monkeypatch.setattr(sys, "argv", ["app.cli", *argv])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    captured = capsys.readouterr()
    status = exit_info.value.code
    return status, captured.out + captured.err + (status if isinstance(status, str) else "")


def _assert_clean(output: str) -> None:
    for value in SENSITIVE:
        assert value not in output, f"output contains {value!r}"
    assert "Traceback" not in output and "[parameters:" not in output and "DETAIL" not in output


def test_database_error_prints_diagnostics_without_stored_values(monkeypatch, capsys):
    # The account appears between the CLI's "does it exist?" check and its
    # INSERT, so PostgreSQL rejects the INSERT with a duplicate-key error whose
    # DETAIL quotes the email, and whose parameters include the password hash.
    monkeypatch.setenv("OWNER_PASSWORD", PASSWORD)
    real_hash = cli.hash_password

    def hash_after_rival_insert(password: str) -> str:
        make_account("customer", EMAIL, name=NAME)
        return real_hash(password)

    monkeypatch.setattr(cli, "hash_password", hash_after_rival_insert)

    status, output = _run(monkeypatch, capsys, "create-owner", EMAIL, "--name", NAME)

    assert status not in (0, None)
    _assert_clean(output)
    # Still enough to diagnose: what kind of error, on which table and rule, and where.
    assert "Command failed (reference " in output
    assert "conflicts with existing data" in output
    assert "db_error=UniqueViolation" in output and "sqlstate=23505" in output
    assert "table_name=accounts" in output and "constraint_name=" in output
    assert "app/cli.py:" in output


def test_duplicate_key_did_not_create_an_owner(monkeypatch, capsys, db):
    monkeypatch.setenv("OWNER_PASSWORD", PASSWORD)
    make_account("customer", EMAIL, name=NAME)
    status, output = _run(monkeypatch, capsys, "create-owner", EMAIL)
    assert "already exists" in output and status not in (0, None)
    assert [a.role for a in db.query(Account).all()] == ["customer"]


def test_unreachable_database_gives_a_hint_not_a_connection_string(monkeypatch, capsys):
    secret_url = "postgresql+psycopg://wendy:SENTINEL-DB-PASSWORD@db.internal:5432/wendy"

    def unreachable(*_args, **_kwargs):
        raise OperationalError("SELECT 1", {}, Exception(f"connection to {secret_url} failed for {EMAIL}"))

    monkeypatch.setattr(cli.limiter, "purge_expired", unreachable)

    status, output = _run(monkeypatch, capsys, "purge-rate-limits")

    assert status not in (0, None)
    _assert_clean(output)
    assert "SENTINEL-DB-PASSWORD" not in output and "db.internal" not in output
    assert "could not be reached" in output and "type=sqlalchemy.exc.OperationalError" in output


def test_non_database_error_prints_type_and_location_only(monkeypatch, capsys):
    def boom(*_args, **_kwargs):
        raise RuntimeError(f"could not process {NAME} <{EMAIL}>")

    monkeypatch.setattr(cli.limiter, "purge_expired", boom)

    status, output = _run(monkeypatch, capsys, "purge-rate-limits")

    assert status not in (0, None)
    _assert_clean(output)
    assert "type=builtins.RuntimeError" in output and "tests/test_cli.py:" in output


def test_menu_file_problems_are_still_explained(monkeypatch, capsys, tmp_path):
    missing = tmp_path / "no-such-menu.json"
    status, output = _run(monkeypatch, capsys, "import-menu", "--file", str(missing))
    assert status not in (0, None)
    assert "Menu file problem" in output and "no-such-menu.json" in output and "Traceback" not in output

    bad = tmp_path / "bad.json"
    bad.write_text('{"categories": []}', encoding="utf-8")
    status, output = _run(monkeypatch, capsys, "import-menu", "--file", str(bad))
    assert "Menu file problem: The menu file has no categories." in output


def test_normal_commands_still_work(monkeypatch, capsys, db):
    monkeypatch.setenv("OWNER_PASSWORD", PASSWORD)
    monkeypatch.setattr(sys, "argv", ["app.cli", "create-owner", "owner.cli@example.com", "--name", "Cli Owner"])
    cli.main()
    assert "Owner account created for owner.cli@example.com." in capsys.readouterr().out
    assert db.query(Account).one().role == "owner"
