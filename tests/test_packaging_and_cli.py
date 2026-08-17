import json
import tomllib

from hub.cli import health_main


def test_pyproject_constrains_package_discovery_and_scripts():
    with open("pyproject.toml", "rb") as handle:
        project = tomllib.load(handle)

    assert project["tool"]["setuptools"]["packages"]["find"]["include"] == ["hub*", "engine*", "agents*", "pipeline*"]
    scripts = project["project"]["scripts"]
    assert scripts["dos-api"] == "hub.cli:api_main"
    assert scripts["dos-health"] == "hub.cli:health_main"


def test_health_cli_prints_json(tmp_path, capsys):
    rc = health_main(["--db", str(tmp_path / "hub.sqlite3"), "--repo-root", "."])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert rc == 0
    assert payload["node_id"] == "local"
    assert payload["status"] in {"healthy", "degraded_local", "repairable_local", "needs_peer_assist", "isolated_but_running", "critical"}
