"""Fixed external randomizer destinations for the webOS TV browser.

These sites pick videos from their own catalogs. No claim of a uniform random
sample of all YouTube uploads, and no private/undocumented JSON API scraping.
"""

from .state import TVError

SERVICES = {
    "random-video": "https://random-video.com/",
    "ytroulette": "https://ytroulette.com/en/",
    "obscuretube": "https://obscuretube.com/",
}

# Only published, navigable YTRoulette category pages are supported.
YTROULETTE_CATEGORIES = frozenset({"music", "sports", "gaming", "zero"})


def randomizer_url(service="random-video", category=None):
    """Return a fixed, audited HTTPS destination; never accept an arbitrary URL."""
    if type(service) is not str or service not in SERVICES:
        raise TVError("Unknown YouTube randomizer service.")
    if category is not None:
        if (
            type(category) is not str
            or service != "ytroulette"
            or category not in YTROULETTE_CATEGORIES
        ):
            raise TVError(
                "Category is supported only by YTRoulette: music, sports, gaming, zero."
            )
        return f"https://ytroulette.com/en/{category}"
    return SERVICES[service]
