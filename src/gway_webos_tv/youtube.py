"""Screenshot-verified navigation of the classic YouTube TV interface.

No account names, live screenshots, or image URLs are stored in the package.
OCR runs locally. Unknown layouts stop with a private diagnostic capture.
"""

import asyncio
import csv
import io
import os
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass

from PIL import Image

from .images import save_image
from .state import TVError


def normalized(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def validate_query(query):
    query = " ".join(query.split()).lower()
    if not query or len(query) > 120:
        raise TVError("Use a YouTube search query between 1 and 120 characters.")
    if re.search(r"[^a-zñ0-9 -]", query):
        raise TVError(
            "YouTube keyboard search supports letters a-z, ñ, digits, spaces, and hyphens."
        )
    return query


@dataclass
class Word:
    text: str
    x: float
    y: float
    width: float
    height: float


@dataclass
class Screen:
    image: Image.Image
    words: list[Word]

    @property
    def text(self):
        return normalized(" ".join(word.text for word in self.words))

    @property
    def footer(self):
        return normalized(
            " ".join(
                word.text for word in self.words if 350 <= word.x < 620 and 210 <= word.y < 250
            )
        )

    @property
    def query(self):
        text = " ".join(
            word.text for word in self.words if 75 <= word.x < 650 and 25 <= word.y < 65
        )
        return "" if normalized(text) in {"buscar", "search"} else normalized(text)

    @property
    def kind(self):
        text = self.text
        if any(
            s in text for s in ("mirar como invitado", "use youtube signed out", "who's watching")
        ):
            return "profiles"
        if any(s in text for s in ("youtube.com/activate", "yt.be/activate", "scan the qr")):
            return "sign-in"
        # Tesseract can omit the black-on-white highlighted button. Two of
        # the three footer controls still identify the keyboard reliably.
        footer = self.footer
        if sum(label in footer for label in ("espacio", "borrar", "buscar")) >= 2 or (
            sum(label in footer for label in ("space", "clear", "delete", "search")) >= 2
        ):
            return "keyboard"
        heading = normalized(" ".join(w.text for w in self.words if w.y < 135))
        if "resultados de la busqueda" in heading or "search results" in heading:
            return "results"
        if any(s in heading for s in ("recomendados", "recommended", "for you", "para ti")):
            return "home"
        return "unknown"

    @property
    def numeric(self):
        digits = sum(
            len(w.text)
            for w in self.words
            if 350 <= w.x < 605 and 80 <= w.y < 215 and w.text.isdigit()
        )
        symbols = sum(
            w.text in {"%", "$", "@", "(", ")", "[", "]", "#", "!", "?"}
            for w in self.words
            if 350 <= w.x < 605 and 80 <= w.y < 215
        )
        return (
            digits >= 5
            or symbols >= 2
            or any(normalized(w.text) == "abc" and w.x > 580 for w in self.words)
        )

    def letter_keys(self):
        spanish = any(label in self.footer for label in ("espacio", "borrar", "buscar"))
        rows = (
            ["ABCDEFG", "HIJKLMN", "ÑOPQRST", "UVWXYZ-"]
            if spanish
            else ["ABCDEFG", "HIJKLMN", "OPQRSTU", "VWXYZ-"]
        )
        return {char.lower(): (r, c) for r, row in enumerate(rows) for c, char in enumerate(row)}

    def digit_keys(self):
        # The numeric/symbol page uses a 3x3 number pad, with zero below it.
        return {
            digit: (row, col)
            for row, digits in enumerate(("123", "456", "789", "0"))
            for col, digit in enumerate(digits)
        }


def read_image(data):
    try:
        return Image.open(io.BytesIO(data)).convert("RGB").resize((960, 540))
    except (OSError, ValueError):
        raise TVError("Could not decode the TV capture.") from None


def read_screen(data):
    try:
        image = read_image(data)
        stream = io.BytesIO()
        image.resize((1920, 1080)).save(stream, format="PNG")
        result = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", "eng", "--psm", "11", "tsv"],
            input=stream.getvalue(),
            capture_output=True,
            timeout=15,
            env={**os.environ, "OMP_THREAD_LIMIT": "1"},
        )
        if result.returncode or len(result.stdout) > 1024 * 1024:
            raise TVError("Local screen recognition failed; check tesseract-ocr-eng.")
        words = []
        for row in csv.DictReader(
            io.StringIO(result.stdout.decode()), delimiter="\t", quoting=csv.QUOTE_NONE
        ):
            if row.get("text", "").strip() and float(row["conf"]) >= 15:
                words.append(
                    Word(
                        row["text"],
                        int(row["left"]) / 2,
                        int(row["top"]) / 2,
                        int(row["width"]) / 2,
                        int(row["height"]) / 2,
                    )
                )
        return Screen(image, words)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        raise TVError("Could not recognize the TV capture locally.") from None


def components(image, box, *, color=False):
    """Find filled keys, profile rings, or colored avatars in a small image region."""
    crop = image.crop(box)
    width = crop.width
    pixels = set()
    data = getattr(crop, "get_flattened_data", crop.getdata)()
    for i, rgb in enumerate(data):
        high, low = max(rgb), min(rgb)
        if (high >= 80 and high - low >= 60) if color else (low >= 210 and high - low < 35):
            pixels.add((i % width, i // width))
    boxes = []
    while pixels:
        start = pixels.pop()
        queue = [start]
        left = right = start[0]
        top = bottom = start[1]
        while queue:
            x, y = queue.pop()
            left, right = min(left, x), max(right, x)
            top, bottom = min(top, y), max(bottom, y)
            for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if point in pixels:
                    pixels.remove(point)
                    queue.append(point)
        boxes.append((left + box[0], top + box[1], right + box[0] + 1, bottom + box[1] + 1))
    return boxes


def keyboard_focus(image):
    boxes = [
        b
        for b in components(image, (350, 80, 645, 250))
        if 20 <= b[2] - b[0] <= 90 and 20 <= b[3] - b[1] <= 38
    ]
    if len(boxes) != 1:
        return None
    left, top, right, bottom = boxes[0]
    x, y = (left + right) / 2, (top + bottom) / 2
    row = min(range(5), key=lambda r: abs(y - (100 + 33 * r)))
    centers = (400, 472, 544) if row == 4 else (373, 406, 439, 472, 505, 539, 572, 615)
    col = min(range(len(centers)), key=lambda c: abs(x - centers[c]))
    return row, col


def search_bar_visible(image):
    # Loading frames can replace the whole browsing surface. Wait for the
    # grey/white search field instead of sending further navigation into them.
    points = ((100, 40), (200, 50), (300, 60))
    return all(min(image.getpixel(point)) >= 25 for point in points)


def first_profile_center(screen):
    # Account labels arrive before avatar artwork on a fresh launch. Group
    # words under each card, excluding the Add account cards and guest button.
    words = sorted((w for w in screen.words if 330 <= w.y < 365), key=lambda w: w.x)
    groups = []
    for word in words:
        if not groups or word.x - (groups[-1][-1].x + groups[-1][-1].width) > 25:
            groups.append([])
        groups[-1].append(word)
    for group in groups:
        label = normalized(" ".join(w.text for w in group))
        if not re.match(r"^(agregar|add)(\s|$)", label):
            return (group[0].x + group[-1].x + group[-1].width) / 2
    avatars = [
        b
        for b in components(screen.image, (0, 130, 960, 370), color=True)
        if 60 <= b[2] - b[0] <= 220 and 60 <= b[3] - b[1] <= 220
    ]
    if avatars:
        first = min(avatars, key=lambda b: b[0])
        return (first[0] + first[2]) / 2
    return None


class YouTube:
    def __init__(self, tv, wait=30):
        self.tv = tv
        self.wait = wait
        self.app = "youtube.leanback.v4"
        self.last_capture = None
        self.selected_profile = False

    @staticmethod
    def check_dependencies():
        if not shutil.which("tesseract"):
            raise TVError("YouTube navigation needs tesseract-ocr and tesseract-ocr-eng installed.")

    async def guard(self):
        if await self.tv.call(self.tv.client.get_current_app()) != self.app:
            raise TVError("YouTube is no longer active; navigation stopped.")

    async def press(self, *keys):
        for key in keys:
            await self.guard()
            await self.tv.press(key)
            await asyncio.sleep(0.2)

    async def snapshot(self, *, ocr=True, previous=None):
        await self.guard()
        await asyncio.sleep(0.35)
        self.last_capture = await self.tv.capture()
        if not ocr:
            image = await asyncio.to_thread(read_image, self.last_capture[0])
            return Screen(image, previous.words if previous else [])
        return await asyncio.to_thread(read_screen, self.last_capture[0])

    async def wait_screen(self, predicate):
        deadline = asyncio.get_running_loop().time() + self.wait
        while True:
            screen = await self.snapshot()
            if screen.kind == "sign-in":
                raise TVError("YouTube needs manual account sign-in; complete it on the TV first.")
            if predicate(screen):
                return screen
            if asyncio.get_running_loop().time() >= deadline:
                raise TVError("The expected YouTube screen was not confirmed.")
            await asyncio.sleep(0.5)

    async def choose_profile(self, screen):
        target = first_profile_center(screen)
        if target is None:
            raise TVError("No saved YouTube profile could be identified; select one on the TV.")
        for _ in range(10):
            rings = [
                b
                for b in components(screen.image, (0, 130, 960, 370))
                if 70 <= b[2] - b[0] <= 230 and 70 <= b[3] - b[1] <= 230
            ]
            if len(rings) == 1:
                center = (rings[0][0] + rings[0][2]) / 2
                if abs(center - target) < 20:
                    await self.press("ENTER")
                    self.selected_profile = True
                    return await self.wait_screen(
                        lambda s: s.kind in {"home", "keyboard", "results"}
                    )
                await self.press("LEFT")
            else:
                await self.press("UP")
            screen = await self.snapshot()
            if screen.kind != "profiles":
                raise TVError("The YouTube profile screen changed before selection.")
        raise TVError("The first saved YouTube profile could not be selected.")

    async def ready(self):
        apps = await self.tv.apps()
        ids = [
            a["id"]
            for a in apps
            if isinstance(a.get("id"), str) and str(a.get("title", "")).casefold() == "youtube"
        ]
        if not ids:
            raise TVError("YouTube is not installed on this TV.")
        self.app = "youtube.leanback.v4" if "youtube.leanback.v4" in ids else ids[0]
        if await self.tv.call(self.tv.client.get_current_app()) != self.app:
            await self.tv.launch(self.app, self.wait)
        screen = await self.snapshot()
        for _ in range(3):
            if screen.kind != "unknown":
                break
            await asyncio.sleep(1)
            screen = await self.snapshot()
        for _ in range(3):
            if screen.kind != "unknown":
                break
            # The first BACK can dismiss playback controls. Another BACK
            # returns to browsing. Never confirm an unrecognized dialog.
            await self.press("BACK")
            for _ in range(3):
                await asyncio.sleep(0.5)
                screen = await self.snapshot()
                if screen.kind != "unknown":
                    break
        if screen.kind == "unknown":
            raise TVError("The YouTube browsing screen could not be identified.")
        if screen.kind == "sign-in":
            raise TVError("YouTube needs manual account sign-in; complete it on the TV first.")
        if screen.kind == "profiles":
            return await self.choose_profile(screen)
        return screen

    async def open_keyboard(self, screen):
        if screen.kind == "results":
            await self.press("BACK")
            return await self.wait_screen(lambda s: s.kind == "keyboard")
        if screen.kind == "keyboard":
            return screen
        # On the home page, moving up reaches the search field. Never select a
        # thumbnail: first confirm that the top search field has the white focus.
        for _ in range(32):
            if not search_bar_visible(screen.image):
                screen = await self.wait_screen(
                    lambda s: s.kind == "home" and search_bar_visible(s.image)
                )
            if any(
                b[2] - b[0] > 150 and b[3] - b[1] > 20
                for b in components(screen.image, (70, 25, 660, 75))
            ):
                await self.press("ENTER")
                return await self.wait_screen(lambda s: s.kind == "keyboard")
            await self.press("UP")
            screen = await self.snapshot(ocr=False, previous=screen)
        raise TVError("Could not focus the YouTube search field.")

    async def focus(self, screen, target):
        target_row, target_col = target
        lost = 0
        for _ in range(16):
            current = keyboard_focus(screen.image)
            if current == target:
                # Native captures can trail the app's focus animation. A
                # second unchanged frame prevents confirming an in-flight key.
                stable = await self.snapshot(ocr=False, previous=screen)
                if keyboard_focus(stable.image) == target:
                    return stable
                screen = stable
                continue
            if current is None:
                lost += 1
                if lost > 1:
                    raise TVError("The selected YouTube keyboard key could not be identified.")
                keys = ["RIGHT"]  # Search suggestions are left of the keyboard.
            else:
                row, col = current
                if row == 4 and target_row < 4:
                    keys = ["UP"]  # Function buttons map to different letter columns.
                else:
                    keys = []
                    if row > target_row:
                        # D/K/Q/X avoids UP on vowels/N and their accent
                        # popups. Send the whole route without capture pauses.
                        keys += ["RIGHT" if col < 3 else "LEFT"] * abs(col - 3)
                        col = 3
                    keys += ["DOWN" if row < target_row else "UP"] * abs(row - target_row)
                    if target_row != 4 or row == 4:
                        keys += ["RIGHT" if col < target_col else "LEFT"] * abs(col - target_col)
            await self.press(*keys)
            screen = await self.snapshot(ocr=False, previous=screen)
            # TVs may coalesce repeated arrows. Recompute the remaining move
            # from the observed focus instead of assuming each key was applied.
        raise TVError("The requested YouTube keyboard key was not confirmed.")

    async def search(self, screen, query):
        if screen.kind == "results" and screen.query == normalized(query):
            return screen
        screen = await self.open_keyboard(screen)
        screen = await self.focus(screen, (4, 1))  # CLEAR / BORRAR clears the entire field.
        await self.press("ENTER")
        screen = await self.wait_screen(lambda s: s.kind == "keyboard" and not s.query)
        for char in query:
            if char == " ":
                target = (4, 0)
            else:
                numeric = char.isdigit()
                if screen.numeric != numeric:
                    screen = await self.focus(screen, (1, 7))  # ABC / &123
                    await self.press("ENTER")
                    screen = await self.wait_screen(
                        lambda s: s.kind == "keyboard" and s.numeric == numeric
                    )
                mapping = screen.digit_keys() if numeric else screen.letter_keys()
                if char not in mapping:
                    raise TVError(
                        "This YouTube keyboard layout cannot enter the requested character."
                    )
                target = mapping[char]
            screen = await self.focus(screen, target)
            await self.press("ENTER")
            screen = await self.snapshot(ocr=False, previous=screen)
        # The app draws grey autocomplete text after a partial query. Verify
        # only after typing the complete query, then verify its results page.
        screen = await self.wait_screen(
            lambda s: s.kind == "keyboard" and s.query == normalized(query)
        )
        await self.focus(screen, (4, 2))  # SEARCH / BUSCAR
        await self.press("ENTER")
        return await self.wait_screen(
            lambda s: s.kind == "results" and s.query == normalized(query)
        )

    async def run(self, query=None):
        try:
            screen = await self.ready()
            if query is not None:
                screen = await self.search(screen, query)
            result = {
                "app_id": self.app,
                "foreground_app": self.app,
                "screen": screen.kind,
                "selected_first_profile": self.selected_profile,
                "verified": True,
            }
            if query is not None:
                result["query"] = query
            return result
        except TVError as error:
            if self.last_capture is not None:
                path = save_image(*self.last_capture, None)
                raise TVError(f"{error} Screen capture: {path}") from None
            raise
