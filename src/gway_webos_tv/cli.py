"""The gway-tv command line."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import __version__
from .client import TV
from .images import save_image
from .state import PERMISSIONS, Device, TVError, default_state_path, load_state, save_state


def seconds(value):
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Use a number of seconds.") from None
    if not 0 < number <= 120:
        raise argparse.ArgumentTypeError("Use a duration between 0 and 120 seconds.")
    return number


def parser():
    root = argparse.ArgumentParser(description="Control a paired webOS TV from GWAY.")
    root.add_argument("--version", action="version", version=__version__)
    root.add_argument(
        "--state", type=Path, default=default_state_path(), help="Private pairing JSON file"
    )
    root.add_argument(
        "--host", help="TV address, or override the saved address with the same certificate"
    )
    root.add_argument(
        "--timeout", type=seconds, default=10, help="Per-operation timeout (default: 10s)"
    )
    root.add_argument("--json", action="store_true", help="Print machine-readable results")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("pair", help="Approve pairing on the TV and save its key privately")
    commands.add_parser("status", help="Read TV identity and foreground input/app")
    commands.add_parser("inputs", help="List the TV's external inputs")
    hdmi = commands.add_parser("hdmi", help="Switch to an HDMI input and verify it is active")
    hdmi.add_argument("number", type=int, choices=range(1, 9), metavar="1-8")
    hdmi.add_argument("--wait", type=seconds, default=30, help="Foreground confirmation timeout")
    capture = commands.add_parser(
        "screenshot", aliases=["sc"], help="Capture the TV's native screen"
    )
    capture.add_argument(
        "output", type=Path, nargs="?", help="New JPEG/PNG file (default: ~/screenshots)"
    )
    commands.add_parser("apps", help="List installed app IDs and names")
    launch = commands.add_parser("launch", help="Launch an app and verify it is in the foreground")
    launch.add_argument("app_id")
    launch.add_argument("--wait", type=seconds, default=30, help="Foreground confirmation timeout")
    youtube = commands.add_parser(
        "youtube", aliases=["yt"], help="Open YouTube and select the first saved profile"
    )
    youtube.set_defaults(command="youtube")
    youtube.add_argument("--wait", type=seconds, default=30, help="Screen readiness timeout")
    actions = youtube.add_subparsers(dest="youtube_command")
    search = actions.add_parser("search", aliases=["s"], help="Search inside the TV's YouTube app")
    search.set_defaults(youtube_command="search")
    search.add_argument("query", nargs="+", help="Search words, quoted or unquoted")
    search.add_argument(
        "--wait", type=seconds, default=argparse.SUPPRESS, help="Screen readiness timeout"
    )
    return root


async def run(args):
    if args.command == "youtube":
        from .youtube import YouTube, validate_query

        query = validate_query(" ".join(args.query)) if args.youtube_command == "search" else None
        YouTube.check_dependencies()
    pairing = args.command == "pair"
    path = args.state.expanduser()
    device = load_state(path, required=not pairing)
    if device is None:
        if not args.host:
            raise TVError("Specify --host TV_ADDRESS for first pairing.")
        device = Device(args.host)
    elif args.host:
        device.host = args.host
    if pairing:
        device.manifest["permissions"] = list(
            dict.fromkeys(device.manifest.get("permissions", []) + PERMISSIONS)
        )
        print("Pairing: approve the connection on the TV if prompted.", file=sys.stderr)
    tv = TV(device, timeout=args.timeout)
    try:
        await tv.connect(pair=pairing)
        if pairing:
            save_state(path, device)
            return {
                "paired": True,
                "host": device.host,
                "model": device.model,
                "state_file": str(path),
            }
        if args.command == "status":
            return await tv.status()
        if args.command == "inputs":
            return {"inputs": await tv.inputs()}
        if args.command == "apps":
            return {"apps": await tv.apps()}
        if args.command == "hdmi":
            return await tv.hdmi(args.number, args.wait)
        if args.command == "launch":
            return await tv.launch(args.app_id, args.wait)
        if args.command == "youtube":
            return await YouTube(tv, wait=args.wait).run(query)
        data, extension = await tv.capture()
        output = save_image(data, extension, args.output)
        return {"path": str(output), "bytes": len(data), "source": "tv", "format": extension[1:]}
    finally:
        await tv.close()


def render(result):
    if "inputs" in result:
        for item in result["inputs"]:
            print(f"{item['id']}\t{item['label']}\tconnected={item['connected']}")
    elif "apps" in result:
        for item in result["apps"]:
            print(f"{item['id']}\t{item['title']}")
    elif "path" in result:
        print(result["path"])
    elif result.get("screen"):
        if "query" in result:
            print(f"YouTube search results: {result['query']}")
        else:
            print("YouTube is ready.")
    elif result.get("verified"):
        print(f"Active: {result.get('label') or result.get('app_id')} ({result['foreground_app']})")
    else:
        for key, value in result.items():
            print(f"{key}={json.dumps(value) if isinstance(value, (dict, bool)) else value}")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = asyncio.run(run(args))
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except (TVError, OSError) as error:
        message = (
            str(error) if isinstance(error, TVError) else "Local file or network operation failed."
        )
        if args.json:
            print(json.dumps({"ok": False, "error": message}))
        else:
            program = "tv" if Path(sys.argv[0]).name == "tv" else "gway-tv"
            print(f"{program}: {message}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result))
    else:
        render(result)
    return 0
