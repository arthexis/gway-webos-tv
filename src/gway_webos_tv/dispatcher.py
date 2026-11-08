"""Canonical TV operations independent of CLI parsing and rendering."""

from dataclasses import dataclass, field
from pathlib import Path

from .state import TVError


OPERATIONS = frozenset({
    "pair", "pair.code", "status", "inputs.list", "inputs.select",
    "apps.list", "apps.launch", "screen.capture", "youtube.open", "youtube.search",
})


@dataclass(frozen=True)
class Operation:
    name: str
    params: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.name not in OPERATIONS:
            raise TVError(f"Unsupported TV operation: {self.name}")


async def dispatch(tv, operation, *, save_capture=None, youtube_factory=None):
    """Execute one canonical operation against an already connected TV.

    Pairing and local interactive pairing codes are deliberately excluded:
    they require a separate trusted local lifecycle, not generic dispatch.
    """
    name, params = operation.name, operation.params
    if name in ("pair", "pair.code"):
        raise TVError("Pairing requires the local interactive CLI lifecycle.")
    if name == "status":
        return await tv.status()
    if name == "inputs.list":
        return {"inputs": await tv.inputs()}
    if name == "inputs.select":
        return await tv.hdmi(params["number"], params["wait"])
    if name == "apps.list":
        return {"apps": await tv.apps()}
    if name == "apps.launch":
        return await tv.launch(params["app_id"], params["wait"])
    if name == "screen.capture":
        if save_capture is None:
            raise TVError("Capture requires an explicit local save handler.")
        data, extension = await tv.capture()
        output = save_capture(data, extension, params.get("output"))
        return {"path": str(output), "bytes": len(data), "source": "tv", "format": extension[1:]}
    if name in ("youtube.open", "youtube.search"):
        if youtube_factory is None:
            raise TVError("YouTube requires an explicit handler.")
        return await youtube_factory(tv, wait=params["wait"]).run(params.get("query"))
    raise TVError(f"Unsupported TV operation: {name}")
