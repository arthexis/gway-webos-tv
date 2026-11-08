"""The gway-tv command line."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import __version__
from .client import TV
from .images import save_image
from .dispatcher import Operation, dispatch
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


def normalize(args):
    """Convert CLI aliases into a canonical operation without executing anything."""
    command = args.command
    if command == "pair":
        return Operation("pair.code" if args.code else "pair")
    if command == "status":
        return Operation("status")
    if command == "inputs":
        command = "inputs.select" if args.inputs_command == "select" else "inputs.list"
    elif command == "hdmi":
        command = "inputs.select"
    elif command == "apps":
        command = "apps.launch" if args.apps_command == "launch" else "apps.list"
    elif command == "launch":
        command = "apps.launch"
    elif command in ("screenshot", "sc", "screen"):
        command = "screen.capture"
    elif command == "youtube":
        command = "youtube.search" if args.youtube_command == "search" else "youtube.open"
    params = {}
    if command == "inputs.select":
        params = {"number": args.number, "wait": args.wait}
    elif command == "apps.launch":
        params = {"app_id": args.app_id, "wait": args.wait}
    elif command == "screen.capture":
        params = {"output": args.output}
    elif command.startswith("youtube."):
        params = {"wait": args.wait}
        if command == "youtube.search":
            params["query"] = " ".join(args.query)
    return Operation(command, params)


async def run(args):
    operation = normalize(args)
    if operation.name.startswith("youtube."):
        from .youtube import YouTube, validate_query

        if operation.name == "youtube.search":
            operation.params["query"] = validate_query(operation.params["query"])
        YouTube.check_dependencies()
    if operation.name == "pair.code":
        if args.json or not sys.stdout.isatty():
            raise TVError("Bridge pairing codes require a private interactive terminal.")
        from .event_bridge import open_local_pairing_window

        code = open_local_pairing_window()
        print("Enter this code on the TV within two minutes:", code, flush=True)
        return None
    pairing = operation.name == "pair"
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
        if operation.name.startswith("youtube."):
            from .youtube import YouTube
        else:
            YouTube = None
        return await dispatch(tv, operation, save_capture=save_image, youtube_factory=YouTube)
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
