"""Download native TV captures without leaking image URLs or overwriting files."""

import http.client
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from .state import TVError

MAX_IMAGE_BYTES = 8 * 1024 * 1024


def validate_image_url(uri: str, host: str, peer_ip: str) -> str:
    try:
        url = urllib.parse.urlsplit(uri)
        valid_port = url.port is None or 1 <= url.port <= 65535
    except (ValueError, TypeError):
        raise TVError("TV returned an invalid capture URL.") from None
    if (
        url.scheme not in {"http", "https"}
        or url.hostname not in {host.lower(), peer_ip.lower()}
        or url.username is not None
        or url.password is not None
        or url.fragment
        or not valid_port
    ):
        raise TVError("Capture URL must point directly to the paired TV.")
    return uri


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def download_image(uri: str, host: str, peer_ip: str, context: ssl.SSLContext, timeout: float):
    validate_image_url(uri, host, peer_ip)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=context),
        NoRedirect(),
    )
    try:
        with opener.open(uri, timeout=timeout) as response:
            data = response.read(MAX_IMAGE_BYTES + 1)
    except (OSError, urllib.error.URLError, ValueError, http.client.HTTPException):
        raise TVError("Could not download the TV capture.") from None
    if len(data) > MAX_IMAGE_BYTES:
        raise TVError("TV capture exceeds the 8 MiB limit.")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return data, ".jpg"
    raise TVError("TV capture is not a JPEG or PNG image.")


def save_image(data: bytes, extension: str, output: Path | None) -> Path:
    if output is None:
        output = (
            Path.home()
            / "screenshots"
            / ("webos-tv-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + extension)
        )
    output = output.expanduser()
    if not output.suffix:
        output = output.with_suffix(extension)
    valid_suffixes = {".jpg", ".jpeg"} if extension == ".jpg" else {".png"}
    if output.suffix.lower() not in valid_suffixes:
        raise TVError(f"TV returned {extension[1:].upper()}; use an {extension} output filename.")
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise TVError("Screenshot output already exists; choose a new filename.") from None
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return output
