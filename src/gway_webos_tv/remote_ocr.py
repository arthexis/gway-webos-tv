"""Read key codes from Remote Test screenshots; useful as an OCR fallback."""

import io
import re
import subprocess

from PIL import Image, ImageOps


def read_code(data):
    with Image.open(io.BytesIO(data)) as image:
        if image.size != (960, 540):
            raise ValueError("Unexpected capture size; cannot reliably read the key code.")
        crop = image.crop((720, 165, 815, 195)).resize((950, 300))
        crop = ImageOps.grayscale(crop).point(lambda pixel: 255 if pixel > 170 else 0)
        output = io.BytesIO()
        crop.save(output, format="PNG")
    result = (
        subprocess.run(
            [
                "tesseract",
                "stdin",
                "stdout",
                "--psm",
                "7",
                "-c",
                "tessedit_char_whitelist=0123456789",
            ],
            input=output.getvalue(),
            capture_output=True,
            check=True,
            timeout=15,
        )
        .stdout.decode("ascii")
        .strip()
    )
    if not re.fullmatch(r"[1-9][0-9]{0,4}", result):
        raise ValueError("No readable key code. Press a button and try again.")
    return int(result)
