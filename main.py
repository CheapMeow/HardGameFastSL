import argparse
import ctypes
import json
import logging
import os
import sys
from ctypes import wintypes
from pathlib import Path

import sekiro

APP_NAME = "HardGameFastSL"
# PyInstaller onefile 的 bootloader 父进程和实际执行逻辑的子进程同名，不能靠进程名计数。
_MUTEX_NAME = "Local\\HardGameFastSL"
_ERROR_ALREADY_EXISTS = 183

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
_kernel32.CloseHandle.restype = wintypes.BOOL

# 句柄必须留到进程结束，系统才会在退出时释放这个 mutex
_instance_lock = None

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


def acquire_single_instance() -> wintypes.HANDLE:
    handle = _kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    last_error = ctypes.get_last_error()
    if not handle:
        raise ctypes.WinError(last_error)
    if last_error == _ERROR_ALREADY_EXISTS:
        if not _kernel32.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())
        logging.error("Another instance is already running")
        raise SystemExit(1)
    return handle


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

    global _instance_lock
    _instance_lock = acquire_single_instance()

    logging.info("Starting pid=%d config=%s", os.getpid(), config_path)
    game_name, game_config = load_game(config_path)
    logging.info("Selected game=%s", game_name)
    GAMES[game_name](game_config)


if __name__ == "__main__":
    main()
