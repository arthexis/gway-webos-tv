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
    pair = commands.add_parser("pair", help="Pair TV control or open a local GWAY Monitor pairing window")
    pair.add_argument("--code", action="store_true", help="Generate a six-digit GWAY Monitor pairing code locally")
    pair_actions = pair.add_subparsers(dest="pair_command")
    pair_actions.add_parser("code", help="Generate a private local interactive pairing code").set_defaults(code=True)
    commands.add_parser("status", help="Read TV identity and foreground input/app")
    inputs = commands.add_parser("inputs", help="List or select external TV inputs")
    input_actions = inputs.add_subparsers(dest="inputs_command")
    input_actions.add_parser("list", help="List the TV's external inputs")
    input_select = input_actions.add_parser("select", help="Select and verify an HDMI input")
    hdmi = commands.add_parser("hdmi", help="Legacy alias for inputs select")
    for select in (input_select, hdmi):
        select.add_argument("number", type=int, choices=range(1, 9), metavar="1-8")
        select.add_argument("--wait", type=seconds, default=30, help="Foreground confirmation timeout")
    screen = commands.add_parser("screen", help="Screen operations")
    screen_actions = screen.add_subparsers(dest="screen_command", required=True)
    screen_capture = screen_actions.add_parser("capture", help="Capture the TV's native screen")
    legacy_capture = commands.add_parser("screenshot", aliases=["sc"], help="Legacy screen capture")
    for capture in (screen_capture, legacy_capture):
        capture.add_argument(
            "output", type=Path, nargs="?", help="New JPEG/PNG file (default: ~/screenshots)"
        )
    apps = commands.add_parser("apps", help="List or manage TV applications")
    apps_actions = apps.add_subparsers(dest="apps_command")
    apps_actions.add_parser("list", help="List installed app IDs, names and versions")
    app_launch = apps_actions.add_parser("launch", help="Launch an app and verify foreground")
    legacy_launch = commands.add_parser("launch", help="Legacy alias for apps launch")
    for launch in (app_launch, legacy_launch):
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
    yts = commands.add_parser("yts", help="Search inside the TV's YouTube app")
    yts.set_defaults(command="youtube", youtube_command="search")
    for search_command, wait_default in ((search, argparse.SUPPRESS), (yts, 30)):
        search_command.add_argument("query", nargs="+", help="Search words, quoted or unquoted")
        search_command.add_argument(
            "--wait", type=seconds, default=wait_default, help="Screen readiness timeout"
        )
    return root


async def run(args):
    if args.command == "youtube":
        from .youtube import YouTube, validate_query

        query = validate_query(" ".join(args.query)) if args.youtube_command == "search" else None
        YouTube.check_dependencies()
    if args.command == "pair" and args.code:
        if args.json or not sys.stdout.isatty():
            raise TVError("Bridge pairing codes require a private interactive terminal.")
        from .event_bridge import open_local_pairing_window

        code = open_local_pairing_window()
        print("Enter this code on the TV within two minutes:", code, flush=True)
        return None
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
        if args.command == "inputs" and args.inputs_command != "select":
            return {"inputs": await tv.inputs()}
        if args.command == "apps" and args.apps_command != "launch":
            return {"apps": await tv.apps()}
        if args.command == "hdmi" or (args.command == "inputs" and args.inputs_command == "select"):
            return await tv.hdmi(args.number, args.wait)
        if args.command == "launch" or (args.command == "apps" and args.apps_command == "launch"):
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
            print(f"{item['id']}\t{item['title']}\tversion={item['version'] or 'unknown'}")
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
    if result is None:
        return 0
    if args.json:
        print(json.dumps(result))
    else:
        render(result)
    return 0
