import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import keyboard
import psutil

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "dist" / "HardGameFastSL.exe"
WORK = ROOT / "work" / "e2e"
# 使用不会被其他程序占用的组合键，避免注入的按键在前台窗口里触发别的功能
HOTKEY = "ctrl+alt+shift+f10"
# 大小写与目标进程名不同，用来验证不区分大小写的匹配
KEYWORD = "E2EVICTIM"


def wait_until(predicate, timeout: float, what: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for: {what}")


def matching_processes() -> list:
    return [p for p in psutil.process_iter(["name"]) if p.info["name"] and KEYWORD.casefold() in p.info["name"].casefold()]


def main() -> None:
    assert EXE.is_file(), f"Build output missing: {EXE}"
    existing = matching_processes()
    assert not existing, f"Processes matching {KEYWORD!r} already running: {[(p.pid, p.info['name']) for p in existing]}"

    if WORK.exists():
        shutil.rmtree(WORK)
    source_dir = WORK / "source"
    target_dir = WORK / "target"
    source_dir.mkdir(parents=True)
    target_dir.mkdir()

    source_save = source_dir / "S0000.sl2"
    source_save.write_bytes(os.urandom(1 << 20))
    target_save = target_dir / "S0000.sl2"
    target_save.write_bytes(b"stale save")

    target_exe = WORK / "E2EVictim.exe"
    shutil.copyfile(Path(os.environ["SystemRoot"]) / "System32" / "PING.EXE", target_exe)

    config_path = WORK / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "Sekiro": {
                    "hotkey": HOTKEY,
                    "process_name_keyword": KEYWORD,
                    "save_source_file": str(source_save),
                    "save_target_dir": str(target_dir),
                    "executable": str(target_exe),
                    "kill_timeout_seconds": 10,
                }
            }
        ),
        encoding="utf-8",
    )
    log_path = WORK / "HardGameFastSL.log"

    def log_text() -> str:
        return log_path.read_text(encoding="utf-8") if log_path.exists() else ""

    tool = subprocess.Popen([str(EXE), "--config", str(config_path)])
    try:
        wait_until(lambda: "Listening hotkey=" in log_text(), 30, "tool listening")

        for round_index in range(1, 3):
            victim = subprocess.Popen(
                [str(target_exe), "-t", "127.0.0.1"],
                stdout=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            time.sleep(0.5)
            assert victim.poll() is None, "Victim process exited before hotkey"
            target_save.write_bytes(b"stale save")

            keyboard.send(HOTKEY)

            wait_until(lambda: victim.poll() is not None, 15, f"victim killed (round {round_index})")
            wait_until(lambda: log_text().count("Launched ") == round_index, 15, f"launch logged (round {round_index})")
            assert target_save.read_bytes() == source_save.read_bytes(), "Target save was not overwritten"
            assert tool.poll() is None, f"Tool exited with code {tool.returncode}"
            print(f"Round {round_index} passed")
    finally:
        print("--- tool log ---")
        print(log_text())
        tool.kill()
        tool.wait()
        for p in matching_processes():
            p.kill()

    print("E2E test passed")


if __name__ == "__main__":
    main()
