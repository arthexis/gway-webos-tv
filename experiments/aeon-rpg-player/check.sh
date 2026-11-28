#!/bin/sh
set -eu
cd "$(dirname "$0")"
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT HUP INT TERM
: "${CC:=cc}"
: "${PKG_CONFIG:=pkg-config}"
"$CC" -std=c99 -Wall -Wextra -Werror test_input.c -o "$out/test_input"
"$out/test_input"
"$CC" -std=c99 -Wall -Wextra -Werror $($PKG_CONFIG --cflags sdl2) controller_probe.c -o "$out/controller_probe" $($PKG_CONFIG --libs sdl2)
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy "$out/controller_probe" --smoke
if command -v ruby >/dev/null 2>&1; then
  ruby generate_fixture.rb "$out/game"
  ruby generate_fixture.rb "$out/game2"
  cmp "$out/game/Game.ini" "$out/game2/Game.ini"
  cmp "$out/game/Data/Scripts.rvdata2" "$out/game2/Data/Scripts.rvdata2"
  ruby -rzlib -e 'a=Marshal.load(File.binread(ARGV[0])); abort unless a.size == 1 && a[0][1] == "AEon smoke" && Zlib::Inflate.inflate(a[0][2]).include?("Graphics.update")' "$out/game/Data/Scripts.rvdata2"
else
  echo 'Fixture generation SKIPPED (Ruby unavailable)' >&2
fi
"$CC" -std=c99 -Wall -Wextra -Werror test_select_hold.c -o "$out/test_select_hold"
"$out/test_select_hold"
"$CC" -std=c99 -Wall -Wextra -Werror test_voice_chord.c -o "$out/test_voice_chord"
"$out/test_voice_chord"
"$CC" -std=c99 -Wall -Wextra -Werror test_voice_intent.c -o "$out/test_voice_intent"
"$out/test_voice_intent"
python3 -m unittest -v test_game_store test_bundle
echo 'Host SDL smoke and input tests PASS'
