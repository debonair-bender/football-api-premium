import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"


def main():
    parser = argparse.ArgumentParser(
        description="Aggiornamento automatico competizioni"
    )

    parser.add_argument(
        "--competition",
        default="all",
        help="Competizione da aggiornare oppure all"
    )

    args = parser.parse_args()

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    competitions = config["competitions"]

    errors = []

    for slug, settings in competitions.items():
        if args.competition != "all" and args.competition != slug:
            continue

        if not settings.get("enabled", False):
            print(f"SKIP: {slug} disabilitata")
            continue

        seasons = settings.get("seasons", {})

        for season, season_config in seasons.items():
            if not season_config.get("enabled", False):
                continue

            # Gli scraper attuali sono configurati
            # esclusivamente per la stagione 2026-2027.
            if season != "2026-2027":
                errors.append(f"{slug}/{season}: non supportata")
                continue

            script = BASE_DIR / settings["script"]

            print(
                f"\nAggiornamento {slug} - {season}",
                flush=True
            )

            result = subprocess.run(
                [sys.executable, str(script)],
                cwd=BASE_DIR,
                check=False
            )

            if result.returncode != 0:
                errors.append(f"{slug}/{season}")
                print(f"ERRORE: {slug}", flush=True)
            else:
                print(f"OK: {slug}", flush=True)

    if errors:
        print(f"Errori: {', '.join(errors)}")
        sys.exit(1)

    print("\nAggiornamento completato!")

if __name__ == "__main__":
    main()
