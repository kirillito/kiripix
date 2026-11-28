#!/usr/bin/env bash
# Slice and sheet generated audio with the 0395 and 0396 Commands, in a scratch Project (not the game's).
#   bash slice-and-sheet.sh out/elevenlabs            # every .mp3/.wav/.flac/.ogg in that folder
# One Asset per generated file (a sound takes one recording per Asset). Sheets land in <folder>/sheets/<name>.png,
# the Take tables in <folder>/sheets/<name>.takes.txt. The scratch Project is scratch-project/ (git-ignored).
# Needs `uv` and a synced kiripix environment (the wheel's ffmpeg decodes MP3). It spends nothing.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
src="${1:?usage: slice-and-sheet.sh <folder of audio>}"
proj="${PROJECT:-$here/scratch-project}"
k() { (cd "$proj" && uv run --project "$repo" kiripix "$@"); }

mkdir -p "$proj"
[ -f "$proj/kiripix.toml" ] || k init . >/dev/null
mkdir -p "$src/sheets"
sheets="$(cd "$src/sheets" && pwd)"
shopt -s nullglob
for f in "$src"/*.mp3 "$src"/*.wav "$src"/*.flac "$src"/*.ogg; do
  stem="$(basename "${f%.*}")"
  name="$(echo "$stem" | tr 'A-Z' 'a-z')"
  [ -d "$proj/assets/sound/$name" ] || k new sound "$name" --use sfx --sound-id "sfx.trial.${name}" >/dev/null
  abs="$(cd "$(dirname "$f")" && pwd)/$(basename "$f")"
  out=$(k import "sound.$name" "$abs" --author "generated, trial 0399" --licence "see findings.md")
  vid=$(echo "$out" | sed -n 's/.*the recording \([0-9a-f]\{16\}\).*/\1/p' | head -1)
  if [ -n "$vid" ]; then k pick "sound.$name" "$vid" >/dev/null; fi
  k run "sound.$name" >/dev/null || true          # `keep` stays needs-input: that is expected
  k sound-takes "sound.$name" > "$sheets/$stem.takes.txt" || true
  k sound-sheet "sound.$name" "$sheets/$stem.png"
  echo "sheet: $sheets/$stem.png"
done
