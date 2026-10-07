"""Regression coverage for upstream bootstrap constraints and secret ownership."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("demo_setup", ROOT / "infra/demo/demo.py")
assert SPEC and SPEC.loader
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


def test_generated_admin_passwords_meet_ehr_policy_and_init_preserves_secrets(
    tmp_path, monkeypatch
):
    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()
    local = tmp_path / "local"
    monkeypatch.setattr(demo, "DEMO", demo_dir)
    monkeypatch.setattr(demo, "LOCAL", local)
    demo.initialize()
    initial = (demo_dir / ".env").read_bytes()
    passwords = dotenv_values(demo_dir / ".env")
    for source in demo.SOURCES:
        password = passwords[f"{source.upper()}_ADMIN_PASSWORD"]
        assert password and len(password) >= 12
        assert any(c.isupper() for c in password)
        assert any(c.islower() for c in password)
        assert any(c.isdigit() for c in password)
        assert password.isalnum()
        config = json.loads((local / f"{source}.json").read_text())
        serialized = json.dumps(config)
        assert all(value not in serialized for value in passwords.values() if value)
        assert config["database"] == source
    demo.initialize()
    assert (demo_dir / ".env").read_bytes() == initial


def test_image_lock_matches_compose_and_never_uses_floating_tags():
    lock = json.loads((ROOT / "infra/demo/images.lock.json").read_text())
    compose = (ROOT / "infra/demo/compose.yaml").read_text()
    for source in ("openmrs", "openemr"):
        for name in ("image", "database_image"):
            image = lock[source][name]
            assert "@sha256:" in image and len(image.split("@sha256:")[1]) == 64
            assert image in compose
    assert ":latest" not in compose
    assert "name: datapulse-m3-demo" in compose
    assert "127.0.0.1:13306:3306" in compose
    assert "127.0.0.1:13307:3306" in compose


def test_ordinary_startup_context_refresh_does_not_trigger_an_install_restart(monkeypatch):
    pending = {
        "openmrs": {"accepted": False, "pinned_metadata_matches": True, "application_ready": False},
        "openemr": {"accepted": True},
    }
    ready = {"openmrs": {"accepted": True}, "openemr": {"accepted": True}}
    states = iter((pending, ready))
    monkeypatch.setitem(
        sys.modules, "verify_environment", SimpleNamespace(verify=lambda: next(states))
    )
    commands = []

    def fake_compose(*args, **kwargs):
        commands.append(args)
        output = "abc123" if args[0] == "ps" else "Done refreshing Context"
        return SimpleNamespace(returncode=0, stdout=output)

    monkeypatch.setattr(demo, "compose", fake_compose)
    monkeypatch.setattr(
        demo.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="2026-10-07T14:00:00Z"),
    )
    monkeypatch.setattr(demo.time, "sleep", lambda seconds: None)
    demo.wait_for_installers()
    assert not any(command[0] == "restart" for command in commands)


def test_unknown_provider_repair_is_idempotent_and_refuses_foreign_configuration(monkeypatch):
    commands = []

    def query(source, sql):
        commands.append(sql)
        return "1\t1\t1"

    monkeypatch.setitem(sys.modules, "verify_environment", SimpleNamespace(query=query))
    assert demo.repair_unknown_provider()
    assert len(commands) == 1 and not any("UPDATE" in sql for sql in commands)
    responses = iter(("1\t1\t0", "0"))
    monkeypatch.setitem(
        sys.modules, "verify_environment", SimpleNamespace(query=lambda *_: next(responses))
    )
    assert not demo.repair_unknown_provider()
    responses = iter(("1\t1\t0", "1", "1"))
    monkeypatch.setitem(
        sys.modules, "verify_environment", SimpleNamespace(query=lambda *_: next(responses))
    )
    assert demo.repair_unknown_provider()


def test_installer_wait_recovers_verified_provider_bootstrap_once(monkeypatch):
    pending = {
        "openmrs": {
            "accepted": False,
            "pinned_metadata_matches": True,
            "database_version": "10.11.7-MariaDB",
            "application_ready": False,
        },
        "openemr": {"accepted": True},
    }
    ready = {"openmrs": {"accepted": True}, "openemr": {"accepted": True}}
    states = iter((pending, ready))
    monkeypatch.setitem(
        sys.modules, "verify_environment", SimpleNamespace(verify=lambda: next(states))
    )
    commands = []

    def compose(*args, **kwargs):
        commands.append(args)
        output = (
            "abc123" if args[0] == "ps" else "Duplicate entry f9badd80-ab76-11e2-9e96-0800200c9a66"
        )
        return SimpleNamespace(returncode=0, stdout=output)

    monkeypatch.setattr(demo, "compose", compose)
    monkeypatch.setattr(demo, "repair_unknown_provider", lambda: True)
    monkeypatch.setattr(
        demo.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout="2026-10-08T00:00:00Z"),
    )
    monkeypatch.setattr(demo.time, "sleep", lambda _: None)
    demo.wait_for_installers()
    assert len([c for c in commands if c[0] == "restart"]) == 1
