"""Split a whole-workspace export into one backup ZIP per event.

`python -m app.cli.export_all` writes each event as events/<id>.zip, byte for
byte the same file the in-app Backup download produces. This script copies
those out under readable names, for an operator who wants to load a single
event by hand (Super Admin ▸ Backup ▸ From backup). Restored that way the
event is named "<name> (Restored)" and starts as a draft.

(Why not download them through the API? In Moimio 1.0.7 the Backup download
fails with HTTP 500 for an event whose name is not Latin-1, e.g. the Korean
event, because the file name goes into a raw Content-Disposition header.)

Usage:
    python split_archive.py moimio-demo-workspace.zip OUT_DIR
"""
import json
import re
import sys
import zipfile
from pathlib import Path

FILE_NAMES = {
    "Youth Retreat 2027": "youth-retreat-2027",
    "Jugendfreizeit 2027": "jugendfreizeit-2027-de",
    "청년부 여름 수련회 2027": "youth-retreat-2027-ko",
}


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(sys.argv[1]) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        for ev in manifest["events"]:
            stem = FILE_NAMES.get(ev["name"]) or re.sub(r"[^a-z0-9]+", "-", ev["name"].lower()).strip("-") or ev["event_id"]
            path = out / f"moimio-backup-{stem}.zip"
            path.write_bytes(zf.read(f"events/{ev['event_id']}.zip"))
            print(f"{path}  {ev['name']}")


if __name__ == "__main__":
    main()
