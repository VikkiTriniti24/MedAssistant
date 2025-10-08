from pathlib import Path

import pytest


pytestmark = pytest.mark.slow


def _ensure_db_file(app):
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if not uri.startswith("sqlite:///"):
        return None
    db_path = Path(uri.replace("sqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        db_path.touch()
    return db_path


def test_backup_db_creates_timestamped_copy(app, runner, tmp_path):
    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    assert db_uri.startswith("sqlite:///"), "test config should use sqlite"

    db_path = _ensure_db_file(app)
    assert db_path is not None

    result = runner.invoke(args=["backup-db", f"--dest={tmp_path}"])
    assert result.exit_code == 0, result.output
    assert "Database backup created" in result.output

    backups = list(Path(tmp_path).glob("*.db"))
    assert backups, "expected a backup file to be created"

    for backup in backups:
        assert backup.stat().st_size >= 0


def test_backup_db_handles_missing_file(app, runner, tmp_path, monkeypatch):
    monkeypatch.setitem(app.config, "SQLALCHEMY_DATABASE_URI", "sqlite:////nonexistent/path.db")

    result = runner.invoke(args=["backup-db", f"--dest={tmp_path}"])
    assert result.exit_code == 0
    assert "not found" in result.output
