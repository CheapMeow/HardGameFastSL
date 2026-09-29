import argparse
import json
import logging
import os
import sys
from pathlib import Path

import sekiro

APP_NAME = "HardGameFastSL"

GAMES = {
    sekiro.GAME_KEY: sekiro.run,
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def load_game(path: Path) -> tuple[str, dict]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict) or len(raw) != 1:
        raise ValueError(f"Config must contain exactly one game key, got: {raw!r}")
    game_name, game_config = next(iter(raw.items()))
    if game_name not in GAMES:
        raise ValueError(f"Unsupported game: {game_name}")
    if not isinstance(game_config, dict):
        raise ValueError(f"Config for {game_name} must be an object")
    return game_name, game_config


def main() -> None:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument("--config", type=Path, default=app_dir() / "config.json")
    args = parser.parse_args()
    config_path: Path = args.config.resolve()

    logging.basicConfig(
        filename=config_path.parent / f"{APP_NAME}.log",
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    previous_excepthook = sys.excepthook

    def log_uncaught(exc_type, exc, tb):
        logging.critical("Uncaught exception", exc_info=(exc_type, exc, tb))
        previous_excepthook(exc_type, exc, tb)

    sys.excepthook = log_uncaught

    logging.info("Starting pid=%d config=%s", os.getpid(), config_path)
    game_name, game_config = load_game(config_path)
    logging.info("Selected game=%s", game_name)
    GAMES[game_name](game_config)


if __name__ == "__main__":
    main()
