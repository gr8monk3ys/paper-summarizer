from __future__ import annotations

import argparse
import os
import shutil
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backup the SQLite database.")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "sqlite:///data/paper_summarizer.db"),
        help="Database URL (sqlite only).",
    )
    parser.add_argument(
        "--backup-dir",
        default="data/backups",
        help="Directory for backups.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=10,
        help="Number of backups to keep.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.database_url.startswith("sqlite:///"):
        raise SystemExit("Only sqlite backups are supported by this script.")

    db_path = Path(args.database_url.replace("sqlite:///", ""))
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"paper_summarizer_{timestamp}.db"

    shutil.copy2(db_path, backup_path)

    backups = sorted(backup_dir.glob("paper_summarizer_*.db"))
    if args.keep and len(backups) > args.keep:
        for old in backups[: len(backups) - args.keep]:
            old.unlink(missing_ok=True)

    print(f"Backup written to {backup_path}")


if __name__ == "__main__":
    main()
