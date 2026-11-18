import base64
import json
import os
import subprocess
from pathlib import Path

from PIL import Image

from gway_webos_tv.image_roll import add_image, image_data, images

ROOT = Path(__file__).resolve().parents[1]


def test_private_bounded_roll(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (40, 40), "red").save(source)
    directory = tmp_path / "roll"
    # More than ten images remain when gaps are shorter than five minutes.
    for i in range(12):
        add_image(source, directory, captured_at=1_700_000_000 + i * 240)
    entries = images(directory)
    assert len(entries) == 1 and len(entries[0]) == 12
    assert entries[0][0]["filename"] == "source.png"
    decoded = base64.b64decode(image_data(entries[0][0]["id"], directory).split(",")[1])
    assert decoded.startswith(b"\xff\xd8")
    assert directory.stat().st_mode & 0o077 == 0
    assert all(p.stat().st_mode & 0o077 == 0 for p in directory.glob("*.jpg"))


def test_rolling_gap_and_ten_set_retention(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), "red").save(source)
    directory = tmp_path / "roll"
    base = 1_700_000_000
    for when in (base, base + 299, base + 598, base + 898):
        add_image(source, directory, captured_at=when)
    groups = images(directory)
    assert [len(group) for group in groups] == [1, 3]
    for i in range(10):
        add_image(source, directory, captured_at=base + 1198 + 300 * i)
    groups = images(directory)
    assert len(groups) == 10
    assert len(list(directory.glob("*.jpg"))) == 10
    assert len(list(directory.glob("*.json"))) == 10


def test_hook_accepts_returned_image_block(tmp_path):
    source = tmp_path / "image.png"
    Image.new("RGB", (4, 4), "blue").save(source)
    event = {
        "tool_response": {
            "content": [{"type": "image", "data": base64.b64encode(source.read_bytes()).decode()}]
        }
    }
    env = {**os.environ, "XDG_STATE_HOME": str(tmp_path / "state")}
    result = subprocess.run(
        [str(Path(os.sys.executable)), str(ROOT / "scripts/image-roll-hook.py")],
        input=json.dumps(event),
        text=True,
        env=env,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert len(list((tmp_path / "state/gway-webos-tv/image-roll").glob("*.jpg"))) == 1
    assert not result.stdout


def test_bridge_only_serves_images_to_monitor_credential(tmp_path, monkeypatch):
    import asyncio
    import hashlib

    import gway_webos_tv.event_bridge as bridge_module
    from gway_webos_tv.event_bridge import Bridge, write_private

    class Socket:
        def __init__(self, credential):
            self.first = json.dumps({"type": "auth", "credential": credential})
            self.request = type("Request", (), {"path": "/"})()
            self.messages = [json.dumps({"type": "monitor.images"})]
            self.sent, self.closed = [], None

        async def recv(self):
            return self.first

        async def send(self, msg):
            self.sent.append(json.loads(msg))

        async def close(self, code, reason):
            self.closed = code

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.messages:
                raise StopAsyncIteration
            return self.messages.pop(0)

    state = tmp_path / "bridge"
    monitor = hashlib.sha256(b"monitor").hexdigest()
    remote = hashlib.sha256(b"remote").hexdigest()
    write_private(
        state / "credential.json",
        {"scoped": {monitor: ["monitor.read"], remote: ["button.pressed"]}},
    )
    monkeypatch.setattr(
        bridge_module, "images", lambda: [{"id": "test", "data": "data:image/jpeg;base64,YQ=="}]
    )
    authorized, denied = Socket("monitor"), Socket("remote")
    asyncio.run(Bridge(state).handler(authorized))
    asyncio.run(Bridge(state).handler(denied))
    assert authorized.sent[-1]["type"] == "monitor.images"
    assert authorized.sent[-1]["images"][0]["id"] == "test"
    assert denied.closed == 1008
    assert all(item["type"] != "monitor.images" for item in denied.sent)


def test_configured_folder_import_and_duplicate_suppression(tmp_path):
    from gway_webos_tv.image_folders import scan_folders

    folder = tmp_path / "captures"
    folder.mkdir()
    child = folder / "android"
    child.mkdir()
    source = child / "screen.png"
    Image.new("RGB", (4, 4), "blue").save(source)
    os.utime(source, (1700000001, 1700000001))
    settings = tmp_path / "folders.json"
    settings.write_text(
        json.dumps({"folders": [{"path": str(folder), "since": 1700000000}, {"path": str(child)}]})
    )
    directory = tmp_path / "roll"
    scan_folders(settings, directory, now=1700000100)
    scan_folders(settings, directory, now=1700000100)
    assert len(images(directory)) == 1
    assert len(images(directory)[0]) == 1
    assert images(directory)[0][0]["filename"] == "screen.png"
    assert (directory / ".folder-index.sqlite").stat().st_mode & 0o077 == 0
