"""Copy your local marketplace (sellers, products, photos) to another computer.

    cd backend
    .venv/Scripts/python scripts/snapshot.py save   # pack demo.db + photos into backend/snapshot/
    git add backend/snapshot && git commit && git push

    # the other computer, after `git pull`:
    python scripts/snapshot.py load                 # unpack into demo.db + uploads/
    python scripts/run_demo.py                      # start the API with that data

`load` refuses to overwrite an existing demo.db unless you pass --force.
Photo links are saved as http://localhost:8000/...; if the API runs at another
address on the new computer (e.g. a VM reached from its host), set API_PUBLIC_URL
in backend/.env before `load` and the links are rewritten to match.
"""

import os
import shutil
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "demo.db"
UPLOADS = BACKEND / "uploads"
SNAP = BACKEND / "snapshot"
SNAP_DB = SNAP / "queneth.db"
SNAP_UPLOADS = SNAP / "uploads"
SAVED_URL = "http://localhost:8000"
MARK = "/media/files/"


def _referenced_files(con: sqlite3.Connection) -> set[str]:
    """Upload paths (relative to uploads/) that any row still points at."""
    found: set[str] = set()
    tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
    for t in tables:
        for _, col, typ, *_rest in con.execute(f"pragma table_info({t})"):
            if "CHAR" not in typ.upper() and "TEXT" not in typ.upper() and typ:
                continue
            rows = con.execute(f'select "{col}" from "{t}" where "{col}" like ?', (f"%{MARK}%",))
            for (v,) in rows:
                if isinstance(v, str):
                    found.add(v.split(MARK, 1)[1].split("?")[0])
    return found


def save() -> None:
    if not DB.exists():
        sys.exit("No backend/demo.db yet. Run scripts/run_demo.py first.")
    if SNAP.exists():
        shutil.rmtree(SNAP)
    SNAP_UPLOADS.mkdir(parents=True)

    # SQLite's backup API gives a consistent copy even while the API is running.
    src = sqlite3.connect(DB)
    dst = sqlite3.connect(SNAP_DB)
    src.backup(dst)
    src.close()
    dst.execute("delete from refresh_tokens")  # sign-in sessions belong to this computer only
    dst.commit()
    dst.execute("vacuum")

    files = _referenced_files(dst)
    dst.close()
    copied = missing = 0
    for rel in sorted(files):
        f = UPLOADS / rel
        if f.is_file():
            (SNAP_UPLOADS / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, SNAP_UPLOADS / rel)
            copied += 1
        else:
            missing += 1
    size = sum(p.stat().st_size for p in SNAP.rglob("*") if p.is_file()) / 1e6
    note = f", {missing} missing" if missing else ""
    print(f"Saved backend/snapshot/ ({size:.1f} MB): database + {copied} photos{note}")


def _public_url() -> str:
    url = os.environ.get("API_PUBLIC_URL")
    env = BACKEND / ".env"
    if not url and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().upper().startswith("API_PUBLIC_URL="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
    return (url or SAVED_URL).rstrip("/")


def load(force: bool) -> None:
    if not SNAP_DB.exists():
        sys.exit("No backend/snapshot/queneth.db. Run `snapshot.py save` on the original computer.")
    if DB.exists() and not force:
        sys.exit("backend/demo.db already exists. Pass --force to replace it with the snapshot.")
    shutil.copy2(SNAP_DB, DB)
    shutil.copytree(SNAP_UPLOADS, UPLOADS, dirs_exist_ok=True)

    url = _public_url()
    if url != SAVED_URL:
        con = sqlite3.connect(DB)
        tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
        for t in tables:
            for _, col, *_rest in con.execute(f"pragma table_info({t})"):
                con.execute(
                    f'update "{t}" set "{col}" = replace("{col}", ?, ?) where "{col}" like ?',
                    (SAVED_URL + "/", url + "/", f"{SAVED_URL}/%"),
                )
        con.commit()
        con.close()
        print(f"Photo links now point at {url}")
    print("Loaded the snapshot into backend/demo.db and uploads/. Start with scripts/run_demo.py")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "save":
        save()
    elif cmd == "load":
        load(force="--force" in sys.argv)
    else:
        sys.exit(__doc__)
