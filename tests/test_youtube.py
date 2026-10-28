"""Synthetic UI stories; never connect to the operator's TV or use its captures."""

import asyncio
import io
import json
import shutil
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw, ImageFont

from gway_webos_tv.cli import parser
from gway_webos_tv.state import TVError
from gway_webos_tv.youtube import Screen, Word, YouTube, keyboard_focus, read_screen, validate_query


def word(text, x=90, y=110):
    return Word(text, x, y, len(text) * 9, 18)


class SyntheticTV:
    def __init__(self, *, page="profiles", foreground="browser", query="", ignore=False):
        self.page, self.foreground, self.query = page, foreground, query
        self.focus = (0, 0)
        self.home_focus = False
        self.presses = []
        self.ignore = ignore
        self.accent = False
        self.client = self

    async def call(self, operation):
        return await operation

    async def get_current_app(self):
        return self.foreground

    async def apps(self):
        return [{"id": "youtube.leanback.v4", "title": "YouTube"}]

    async def launch(self, app, wait):
        self.foreground = app

    async def press(self, key):
        self.presses.append(key)
        if self.ignore:
            return
        row, col = self.focus
        if self.page == "profiles" and key == "ENTER":
            self.page = "home"
        elif self.page == "video" and key == "BACK":
            self.page = "home"
        elif self.page == "home":
            if key == "UP":
                self.home_focus = True
            elif key == "ENTER":
                assert self.home_focus, "Must not select a home-page video"
                self.page = "keyboard"
        elif self.page == "results" and key == "BACK":
            self.page, self.focus = "keyboard", (0, 0)
        elif self.page == "keyboard":
            if self.accent:
                if key == "ENTER":
                    self.query += "ñ"
                    self.accent = False
                    self.focus = (1, 6)
                    return
                if key == "DOWN":
                    self.accent = False
                    self.focus = (1, 6)
                    return
            if key == "UP" and (row, col) == (1, 6):
                self.accent = True
                self.focus = (0, 6)  # The popup overlaps G's normal coordinates.
                return
            if key == "DOWN":
                row = min(4, row + 1)
                if row == 4:
                    col = min(range(3), key=lambda c: abs((400, 472, 544)[c] - (373 + 33 * col)))
            elif key == "UP":
                if row == 4:
                    col = (1, 3, 5)[col]
                row = max(0, row - 1)
            elif key == "LEFT":
                col = max(0, col - 1)
            elif key == "RIGHT":
                col = min(2 if row == 4 else 6, col + 1)
            elif key == "ENTER":
                if row < 4:
                    self.query += ("abcdefg", "hijklmn", "ñopqrst", "uvwxyz-")[row][col]
                elif col == 0:
                    self.query += " "
                elif col == 1:
                    self.query = ""
                else:
                    self.page = "results"
            self.focus = row, col

    def screen(self):
        image = Image.new("RGB", (960, 540), "#101010")
        draw = ImageDraw.Draw(image)
        if self.page == "profiles":
            draw.ellipse((40, 160, 210, 330), fill="white")
            draw.ellipse((45, 165, 205, 325), fill="purple")
            return Screen(image, [word("Mirar como invitado", y=465)])
        if self.page == "sign-in":
            return Screen(image, [word("youtube.com/activate")])
        words = [word(self.query or "Buscar", y=40)]
        draw.rounded_rectangle((80, 33, 640, 69), 15, fill="#303030")
        if self.page == "home":
            words.append(word("Recomendados"))
            if self.home_focus:
                draw.rounded_rectangle((80, 33, 640, 69), 15, fill="white")
        elif self.page == "results":
            words.append(word("Resultados de la búsqueda de " + self.query))
        elif self.page == "keyboard":
            words.extend([word("ESPACIO", 367, 225), word("BORRAR", 440, 225)])
            row, col = self.focus
            x = (400, 472, 544)[col] if row == 4 else (373 + 33 * col)
            y = 100 + 33 * row
            width = 66 if row == 4 else 26
            draw.rounded_rectangle((x - width / 2, y - 13, x + width / 2, y + 13), 3, fill="white")
        return Screen(image, words)


class Workflow(YouTube):
    async def snapshot(self, **kwargs):
        await self.guard()
        return self.tv.screen()


def test_switch_apps_select_first_profile_and_search_without_starting_video(monkeypatch):
    async def no_sleep(seconds):
        pass

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    tv = SyntheticTV()
    result = asyncio.run(Workflow(tv).run("chatgpt codex"))
    assert result["verified"] and result["selected_first_profile"]
    assert tv.foreground == "youtube.leanback.v4"
    assert tv.page == "results" and tv.query == "chatgpt codex"


def test_saved_profile_can_be_selected_before_avatar_images_load(monkeypatch):
    async def no_sleep(seconds):
        pass

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    class MissingAvatarTV(SyntheticTV):
        def screen(self):
            screen = super().screen()
            if self.page == "profiles":
                ImageDraw.Draw(screen.image).ellipse((45, 165, 205, 325), fill="#101010")
                screen.words.extend(
                    [Word("Member", 95, 345, 60, 18), Word("Add account", 550, 345, 100, 18)]
                )
            return screen

    tv = MissingAvatarTV()
    assert asyncio.run(Workflow(tv).run())["selected_first_profile"]


def test_search_replaces_existing_query(monkeypatch):
    async def no_sleep(seconds):
        pass

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    tv = SyntheticTV(page="results", foreground="youtube.leanback.v4", query="old query")
    result = asyncio.run(Workflow(tv).run("new"))
    assert result["query"] == "new" and tv.query == "new"
    assert not result["selected_first_profile"]


def test_repeated_search_is_idempotent():
    tv = SyntheticTV(page="results", foreground="youtube.leanback.v4", query="chatgpt")
    assert asyncio.run(Workflow(tv).run("chatgpt"))["verified"]
    assert tv.presses == []


def test_resumed_video_returns_to_browsing_before_search(monkeypatch):
    async def no_sleep(seconds):
        pass

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    tv = SyntheticTV(page="video", foreground="youtube.leanback.v4")
    assert asyncio.run(Workflow(tv).run("chatgpt"))["verified"]
    assert tv.presses[0] == "BACK" and tv.page == "results"


def test_digit_mode_is_read_from_visible_keyboard_labels():
    image = Image.new("RGB", (960, 540), "black")
    screen = Screen(
        image,
        [
            word("ESPACIO", 367, 225),
            word("BORRAR", 440, 225),
            word("ABC", 605, 130),
            Word("1234567", 365, 90, 215, 20),
            Word("890", 365, 123, 83, 20),
        ],
    )
    assert screen.numeric
    assert screen.digit_keys()["1"] == (0, 0)
    assert screen.digit_keys()["5"] == (1, 1)
    assert screen.digit_keys()["7"] == (2, 0)
    assert screen.digit_keys()["0"] == (3, 0)


def test_ocr_tsv_quotes_are_literal_and_do_not_swallow_following_rows(monkeypatch):
    rows = ["level\tleft\ttop\twidth\theight\tconf\ttext"]
    for text, x, y in [
        ('"', 1140, 320),
        ("%", 940, 390),
        ("]", 1140, 390),
        ("ESPACIO", 750, 450),
        ("BORRAR", 900, 450),
        ("BUSCAR", 1040, 450),
    ]:
        rows.append(f"5\t{x}\t{y}\t50\t20\t95\t{text}")
    monkeypatch.setattr(
        "gway_webos_tv.youtube.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=("\n".join(rows) + "\n").encode()),
    )
    image = Image.new("RGB", (960, 540), "black")
    stream = io.BytesIO()
    image.save(stream, "PNG")
    screen = read_screen(stream.getvalue())
    assert len(screen.words) == 6
    assert screen.words[0].text == '"'
    assert screen.kind == "keyboard" and screen.numeric


@pytest.mark.parametrize("omitted", ["ESPACIO", "BORRAR", "BUSCAR"])
def test_keyboard_recognition_tolerates_missing_highlighted_label(omitted):
    image = Image.new("RGB", (960, 540), "black")
    screen = Screen(
        image,
        [
            word(label, 367 + 72 * i, 225)
            for i, label in enumerate(("ESPACIO", "BORRAR", "BUSCAR"))
            if label != omitted
        ],
    )
    assert screen.kind == "keyboard"
    assert screen.letter_keys()["p"] == (2, 2)


def test_account_challenge_never_gets_confirmed():
    tv = SyntheticTV(page="sign-in", foreground="youtube.leanback.v4")
    with pytest.raises(TVError, match="manual account sign-in"):
        asyncio.run(Workflow(tv).run("chatgpt"))
    assert tv.presses == []


def test_app_switch_during_a_button_sequence_stops_remaining_input():
    class ChangedTV(SyntheticTV):
        async def press(self, key):
            self.presses.append(key)
            self.foreground = "another-app"

    tv = ChangedTV(foreground="youtube.leanback.v4")
    with pytest.raises(TVError, match="no longer active"):
        asyncio.run(Workflow(tv).press("UP", "UP"))
    assert tv.presses == ["UP"]


def test_coalesced_arrow_events_are_retried_from_observed_focus(monkeypatch):
    async def no_sleep(seconds):
        pass

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    class DroppingTV(SyntheticTV):
        count = 0

        async def press(self, key):
            self.count += 1
            if self.count % 2:
                await super().press(key)

    tv = DroppingTV(page="keyboard", foreground="youtube.leanback.v4")
    result = asyncio.run(Workflow(tv).focus(tv.screen(), (2, 5)))
    assert keyboard_focus(result.image) == (2, 5)


def test_t_to_g_avoids_the_n_accent_popup(monkeypatch):
    async def no_sleep(seconds):
        pass

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    tv = SyntheticTV(page="keyboard", foreground="youtube.leanback.v4", query="chat")
    tv.focus = (2, 6)  # T

    async def scenario():
        workflow = Workflow(tv)
        await workflow.focus(tv.screen(), (0, 6))  # G
        await workflow.press("ENTER")

    asyncio.run(scenario())
    assert tv.query == "chatg" and not tv.accent


def test_acknowledged_but_ignored_profile_selection_is_not_success():
    tv = SyntheticTV(ignore=True)
    with pytest.raises(TVError, match="not confirmed"):
        asyncio.run(Workflow(tv, wait=0.001).run("chatgpt"))


def test_missing_input_permissions_fail_before_opening_socket():
    from gway_webos_tv.client import TV
    from gway_webos_tv.state import Device

    device = Device("192.0.2.50")
    device.manifest["permissions"].remove("CONTROL_MOUSE_AND_KEYBOARD")
    with pytest.raises(TVError, match="tv pair"):
        asyncio.run(TV(device).press("ENTER"))


@pytest.mark.parametrize("query", ["", "  ", "x" * 121, "unsupported\n🙂"])
def test_invalid_search_fails_before_tv_actions(query):
    with pytest.raises(TVError):
        validate_query(query)


def test_alias_and_unquoted_search_words():
    assert parser().parse_args(["sc"]).command == "sc"
    args = parser().parse_args(["youtube", "search", "chatgpt", "codex"])
    assert validate_query(" ".join(args.query)) == "chatgpt codex"
    assert parser().parse_args(["youtube", "--wait", "60", "search", "chatgpt"]).wait == 60


@pytest.mark.parametrize(
    "command,query",
    [
        (["youtube"], None),
        (["yt"], None),
        (["youtube", "search", "chatgpt", "codex"], "chatgpt codex"),
        (["youtube", "s", "chatgpt", "codex"], "chatgpt codex"),
        (["yt", "search", "chatgpt", "codex"], "chatgpt codex"),
        (["yt", "s", "chatgpt", "codex"], "chatgpt codex"),
    ],
)
def test_cli_short_and_long_forms_run_youtube_instead_of_capture(
    command, query, tmp_path, monkeypatch, capsys
):
    from gway_webos_tv.cli import main
    from gway_webos_tv.state import Device, save_state

    state = tmp_path / "device.json"
    save_state(state, Device("192.0.2.50", "test-pairing-key", "a" * 64))
    calls = []

    class FakeTV:
        def __init__(self, device, timeout):
            pass

        async def connect(self, **kwargs):
            calls.append("connect")

        async def close(self):
            calls.append("close")

        async def capture(self):
            raise AssertionError("YouTube aliases must not fall through to screen capture")

    class FakeYouTube:
        def __init__(self, tv, wait):
            pass

        @staticmethod
        def check_dependencies():
            pass

        async def run(self, actual_query):
            calls.append(actual_query)
            return {"screen": "results" if actual_query else "home", "query": actual_query}

    monkeypatch.setattr("gway_webos_tv.cli.TV", FakeTV)
    monkeypatch.setattr("gway_webos_tv.youtube.YouTube", FakeYouTube)
    assert main(["--state", str(state), "--json", *command]) == 0
    assert calls == ["connect", query, "close"]
    assert json.loads(capsys.readouterr().out)["query"] == query


def test_ambiguous_keyboard_focus_is_rejected():
    image = Image.new("RGB", (960, 540), "black")
    draw = ImageDraw.Draw(image)
    for x in (373, 406):
        draw.rectangle((x - 13, 87, x + 13, 113), fill="white")
    assert keyboard_focus(image) is None


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Local Tesseract is not installed")
def test_real_local_ocr_reads_query_and_results_heading():
    image = Image.new("RGB", (960, 540), "#101010")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=24)
    draw.text((95, 35), "chatgpt", font=font, fill="white")
    draw.text((80, 105), "Search results for chatgpt", font=font, fill="white")
    data = io.BytesIO()
    image.save(data, "PNG")
    screen = read_screen(data.getvalue())
    assert screen.kind == "results" and screen.query == "chatgpt"
