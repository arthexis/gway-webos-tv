import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from gway_webos_tv.images import download_image, save_image, validate_image_url
from gway_webos_tv.state import TVError


@pytest.mark.parametrize(
    "uri",
    [
        "file:///etc/passwd",
        "http://192.0.2.51/capture.jpg",
        "https://192.0.2.50.attacker.invalid/capture.jpg",
        "http://user:password@192.0.2.50/capture.jpg",
        "http://192.0.2.50:99999/capture.jpg",
    ],
)
def test_capture_url_stays_on_tv(uri):
    with pytest.raises(TVError):
        validate_image_url(uri, "192.0.2.50", "192.0.2.50")


def test_format_and_no_overwrite(tmp_path):
    data = b"\xff\xd8\xfftest-image"
    with pytest.raises(TVError, match="JPEG|JPG"):
        save_image(data, ".jpg", tmp_path / "wrong.png")
    assert not (tmp_path / "wrong.png").exists()
    output = save_image(data, ".jpg", tmp_path / "capture")
    assert output.suffix == ".jpg"
    assert output.stat().st_mode & 0o777 == 0o600
    with pytest.raises(TVError, match="already exists"):
        save_image(b"replacement", ".jpg", output)
    assert output.read_bytes() == data


def test_download_rejects_redirect_and_html():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "http://192.0.2.51/private-capture")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<html>not a capture</html>")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for route in ["redirect", "html"]:
            with pytest.raises(TVError):
                download_image(
                    f"http://127.0.0.1:{server.server_port}/{route}",
                    "127.0.0.1",
                    "127.0.0.1",
                    ssl.create_default_context(),
                    2,
                )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
