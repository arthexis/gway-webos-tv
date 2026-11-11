"""Offline browser tests: only synthetic data; never contact the TV or publish its captures."""
import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parents[1] / "apps/gway-monitor/index.html"


def fixtures():
    prs = {"repositories": ["example/repo"] * 10, "pull_requests": [
        {"repo": "example/csms", "number": 333, "draft": True, "ci": "passed",
         "merge": "CLEAN", "title": "Phase C release isolation and fail-safe cutover with a very long descriptive GitHub pull request title that must remain readable without truncating evidence"},
        {"repo": "example/agent-ops", "number": 73, "draft": True, "ci": "failed",
         "merge": "BLOCKED", "title": "Fix durable uncertain launch and recovery reporting"},
        {"repo": "example/simulator", "number": 20, "draft": False, "ci": "pending",
         "merge": "BEHIND", "title": "Recover multi-connector simulator"},
    ]}
    values = [
        ("csms", "a" * 40, "activated", "healthy", "2026-11-11T07:00:00Z"),
        ("reports", None, "unknown", "unhealthy", None),
        ("sound", "b" * 40, "activated", "healthy", "2026-11-09T07:00:00Z"),
        ("agents", "c" * 40, "activated", "not_applicable", "2026-11-08T07:00:00Z"),
        ("kiosk", "d" * 40, "activated", "healthy", None),
        ("rfid", "e" * 40, "activated", "healthy", "2026-11-07T07:00:00Z"),
        ("bastion", None, "staged", "not_applicable", None),
    ]
    components = [
        {"name": n, "repository": "example/" + n, "revision": rev,
         "installation": install, "health": health, "deployed_at": date}
        for n, rev, install, health, date in values
    ]
    components[1]["error"] = "Collector unavailable: preserve the complete error"
    components[3].update(runtime_required=False, verified_release=True)
    return prs, {"available": True, "node": "test-appliance", "components": components}


def output_dir(tmp_path):
    directory = Path(os.environ.get("GWAY_TV_SCREENSHOT_DIR", str(tmp_path)))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def selected(page):
    return page.evaluate("""() => Array.from(document.querySelectorAll('#deployment-list > article'))
        .findIndex(c => c.classList.contains('selected-card'))""")


@pytest.mark.parametrize("width,height", [(1920, 1080), (960, 540)])
def test_responsive_layout_and_remote_controls(tmp_path, width, height):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        outbound = []
        page.on("request", lambda req: outbound.append(req.url)
                if req.url.startswith(("http:", "https:", "ws:", "wss:")) else None)
        page.goto(APP.as_uri(), wait_until="load")
        prs, deployments = fixtures()
        page.evaluate("""data => {
            window.GwayMonitorChannels.github.render(data.prs);
            window.GwayMonitorChannels.deployments.render(data.deployments);
        }""", {"prs": prs, "deployments": deployments})
        assert not outbound, "Fixtures must never use the network"
        page.keyboard.press("PageUp")
        page.keyboard.press("PageUp")
        assert page.locator("#title").inner_text() == "GitHub PRs"
        titles = page.locator("#pr-list .github-title")
        assert titles.count() == 3
        assert float(titles.first.evaluate("e => parseFloat(getComputedStyle(e).fontSize)")) >= 30
        assert titles.first.inner_text() == prs["pull_requests"][0]["title"]
        assert page.locator("#pr-list .tv-chip").count() == 9
        assert page.locator("#pr-list [aria-label='CI: failed']").count() == 1
        assert page.locator("#pr-list [aria-label='Merge: BLOCKED']").count() == 1
        # 'Open' is a neutral lifecycle label, not a green 'passed' indicator.
        open_chip = page.locator("#pr-list [aria-label='State: Open']")
        assert open_chip.count() == 1
        assert "status-open" in open_chip.get_attribute("class")
        assert "status-passed" not in open_chip.get_attribute("class")
        for card in page.locator("#pr-list .github-card").all():
            rect = card.bounding_box()
            assert rect["x"] >= 0 and rect["x"] + rect["width"] <= width + 1
            assert rect["width"] >= width * 0.85, "PR cards stay full-width"
        page.screenshot(path=str(output_dir(tmp_path) / f"prs-{width}x{height}.png"))
        page.keyboard.press("ArrowDown")
        assert page.locator("#pr-list .selected-card .github-repo").inner_text().endswith("#73")
        page.keyboard.press("PageUp")
        assert page.locator("#title").inner_text() == "Deployments"
        cards = page.locator("#deployment-list .deployment-card")
        assert cards.count() == 7
        box = [card.bounding_box() for card in cards.all()]
        if width >= 1200:
            assert abs(box[0]["y"] - box[1]["y"]) < 2
            assert box[2]["y"] > box[0]["y"] and box[0]["width"] < width * .49
        else:
            assert box[1]["y"] > box[0]["y"]
            assert abs(box[0]["x"] - box[1]["x"]) < 2
        assert float(cards.first.locator(".deployment-name").evaluate(
            "e => parseFloat(getComputedStyle(e).fontSize)")) >= 29
        assert cards.first.locator(".deployment-sha").inner_text() == "a" * 12 + "…"
        assert cards.first.locator(".deployment-sha").get_attribute("data-full-revision") == "a" * 40
        assert cards.first.locator(".deployment-full-revision").is_visible()
        assert "preserve the complete error" in cards.nth(1).locator(".deployment-error").inner_text()
        na_chip = cards.nth(6).locator("[aria-label='Health: not_applicable']")
        assert na_chip.count() == 1
        assert "status-na" in na_chip.get_attribute("class")
        idle_chip = cards.first.locator("[aria-label='Retry: Not needed']")
        assert "status-idle" in idle_chip.get_attribute("class")
        assert all(card.locator(".tv-chip").count() == 3 for card in cards.all())
        # All seven compact cards fit at full-HD without obscuring the fixed footer.
        if width >= 1200:
            viewport = page.locator("#deployments").bounding_box()
            assert box[6]["y"] + box[6]["height"] <= viewport["y"] + viewport["height"] + 1
        # The count and independent pairing hint must not collide.
        count = page.locator("#channel-count").bounding_box()
        hint = page.locator("#reconnect-hint").bounding_box()
        if hint is not None:
            assert count["x"] + count["width"] <= hint["x"] + 1
        page.screenshot(path=str(output_dir(tmp_path) / f"deployments-{width}x{height}.png"))
        assert selected(page) == 0
        if width >= 1200:
            for key, index in (("ArrowRight", 1), ("ArrowDown", 3),
                               ("ArrowLeft", 2), ("ArrowUp", 0)):
                page.keyboard.press(key)
                assert selected(page) == index
            page.keyboard.press("ArrowRight")
            assert selected(page) == 1
            page.keyboard.press("ArrowUp")
            assert selected(page) == 1, "Up from top-right must not jump left"
            page.keyboard.press("ArrowDown")
            page.keyboard.press("ArrowDown")
            assert selected(page) == 5
            page.keyboard.press("ArrowDown")
            assert selected(page) == 5, "No lower-right cell in an odd final row"
            page.keyboard.press("ArrowLeft")
            assert selected(page) == 4
            page.keyboard.press("ArrowDown")
            assert selected(page) == 6
            page.keyboard.press("ArrowRight")
            assert selected(page) == 6, "No right-hand cell in final row"
            page.keyboard.press("ArrowUp")
            page.keyboard.press("ArrowUp")
            assert selected(page) == 2
            page.keyboard.press("ArrowUp")
            assert selected(page) == 0
        else:
            for key, index in (("ArrowRight", 0), ("ArrowDown", 1), ("ArrowUp", 0)):
                page.keyboard.press(key)
                assert selected(page) == index
        page.evaluate("""() => { window.__retry=[];
            window.GwayMonitorChannels.deployments.setRetry(n => {
                window.__retry.push(n); return true; }); }""")
        page.keyboard.press("ArrowRight" if width >= 1200 else "ArrowDown")
        assert selected(page) == 1
        page.keyboard.press("Enter")
        assert page.evaluate("window.__retry") == ["reports"]
        assert cards.nth(1).locator("[aria-label='Retry: Running']").count() == 1
        assert page.evaluate("document.scrollingElement.scrollTop") == 0
        assert not outbound
        browser.close()


def test_synthetic_comparison_images(tmp_path):
    # The second test uses the shared CI output directory. No TV data is used.
    if not os.environ.get("GWAY_TV_SCREENSHOT_DIR"):
        pytest.skip("Shared screenshot output is configured in dedicated browser CI")
    folder = output_dir(tmp_path)
    for name in ("prs", "deployments"):
        wide = Image.open(folder / (name + "-1920x1080.png")).convert("RGB")
        narrow = Image.open(folder / (name + "-960x540.png")).convert("RGB")
        assert wide.size == (1920, 1080) and narrow.size == (960, 540)
        sampled = wide.resize((80, 45))
        assert len({sampled.getpixel((x, y)) for x in range(80) for y in range(45)}) >= 25
        compare = Image.new("RGB", (1920, 590), "#0b1524")
        compare.paste(wide.resize((960, 540)), (0, 45))
        compare.paste(narrow, (960, 45))
        ink = ImageDraw.Draw(compare)
        ink.text((20, 12), "1920x1080 at 50%", fill="white")
        ink.text((980, 12), "960x540 native", fill="white")
        compare.save(folder / (name + "-comparison.png"))


def test_empty_unknown_and_overflow_never_scroll_the_document():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 960, "height": 540})
        page.goto(APP.as_uri(), wait_until="load")
        page.evaluate("""() => window.GwayMonitorChannels.github.render({
            repositories: ["example/a"], pull_requests: []})""")
        assert "No open PRs" in page.locator("#pr-list").inner_text()
        page.evaluate("() => window.GwayMonitorChannels.github.render(null)")
        assert page.locator("#pr-summary").inner_text() == "Unavailable"
        page.evaluate("() => window.GwayMonitorChannels.deployments.render({available:false})")
        assert page.locator("#deployment-summary").inner_text() == "Deployment data unavailable"
        prs, data = fixtures()
        page.evaluate("v => window.GwayMonitorChannels.deployments.render(v)", data)
        for _ in range(3):
            page.keyboard.press("PageUp")
        assert page.locator("#title").inner_text() == "Deployments"
        for _ in range(6):
            page.keyboard.press("ArrowDown")
        assert selected(page) == 6
        assert page.locator("#deployments").evaluate("e => e.scrollTop") > 0
        assert page.evaluate("document.scrollingElement.scrollTop") == 0
        page.evaluate("v => window.GwayMonitorChannels.deployments.render(v)", data)
        assert selected(page) == 6, "Refresh must preserve remote selection"
        prs["pull_requests"][0]["title"] = "<img src=x onerror=window.__injected=1>"
        page.evaluate("v => window.GwayMonitorChannels.github.render(v)", prs)
        assert page.locator("#pr-list img").count() == 0
        assert page.evaluate("window.__injected === undefined")
        browser.close()
