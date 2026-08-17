import json
from pathlib import Path

from hub.storage.db import Database
from hub.storage.top_of_mind_repo import TopOfMindRepo


def test_numbering_registry_has_expected_high_frequency_codes():
    registry_path = Path("config/numbering/top_of_mind_numbering.v1.json")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    assert registry["ports"]["file_intelligence_hub"]["default"] == 10000
    assert registry["sources"]["22001"]["callsign"] == "clipboard"
    assert registry["sources"]["20040"]["callsign"] == "codex"
    assert registry["message_types"]["32001"] == "clip-capture"
    assert registry["priorities"]["40003"]["name"] == "normal"
    assert registry["walls"]["50001"] == "main"
    assert registry["folders"]["60001"] == "Inbox"


def test_top_message_persists_numbering_codes(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    repo = TopOfMindRepo(db.conn)

    message = repo.post_message(
        source_id="clipboard",
        source_label="Clipboard",
        source_code=22001,
        type_code=32001,
        priority=3,
        priority_code=40003,
        wall="main",
        wall_code=50001,
        folder="Inbox",
        folder_code=60001,
        body="clipboard text",
    )

    assert message["source_code"] == 22001
    assert message["type_code"] == 32001
    assert message["priority_code"] == 40003
    assert message["wall_code"] == 50001
    assert message["folder_code"] == 60001
