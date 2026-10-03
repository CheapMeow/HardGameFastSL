import logging
import queue
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

import keyboard
import psutil

GAME_KEY = "Sekiro"


@dataclass(frozen=True)
class Config:
    hotkey: str
    process_name_keyword: str
    save_source_file: Path
    save_target_dir: Path
    executable: Path
    kill_timeout_seconds: float
    backup_hotkey: str
    backup_source_file: Path
    backup_target_dir: Path


def load_config(raw: dict) -> Config:
    raw = dict(raw)
    config = Config(
        hotkey=raw.pop("hotkey"),
        process_name_keyword=raw.pop("process_name_keyword"),
        save_source_file=Path(raw.pop("save_source_file")),
        save_target_dir=Path(raw.pop("save_target_dir")),
        executable=Path(raw.pop("executable")),
        kill_timeout_seconds=float(raw.pop("kill_timeout_seconds")),
        backup_hotkey=raw.pop("backup_hotkey"),
        backup_source_file=Path(raw.pop("backup_source_file")),
        backup_target_dir=Path(raw.pop("backup_target_dir")),
    )
    if raw:
        raise ValueError(f"Unknown config keys: {sorted(raw)}")
    if not config.process_name_keyword:
        raise ValueError("process_name_keyword must not be empty")
    if not config.save_source_file.is_file():
        raise FileNotFoundError(f"save_source_file not found: {config.save_source_file}")
    if not config.save_target_dir.is_dir():
        raise NotADirectoryError(f"save_target_dir not found: {config.save_target_dir}")
    if not config.executable.is_file():
        raise FileNotFoundError(f"executable not found: {config.executable}")
    if not config.backup_hotkey:
        raise ValueError("backup_hotkey must not be empty")
    if not config.backup_target_dir.is_dir():
        raise NotADirectoryError(f"backup_target_dir not found: {config.backup_target_dir}")
    keyboard.parse_hotkey(config.hotkey)
    keyboard.parse_hotkey(config.backup_hotkey)
    return config


def kill_processes(keyword: str, timeout: float) -> None:
    keyword = keyword.casefold()
    # 排除本进程及其父进程，避免关键字命中本程序或 PyInstaller onefile 的 bootloader
    me = psutil.Process()
    excluded = {me.pid} | {p.pid for p in me.parents()}
    targets = [
        p
        for p in psutil.process_iter(["name"])
        if p.pid not in excluded and p.info["name"] and keyword in p.info["name"].casefold()
    ]
    for p in targets:
        logging.info("Killing pid=%d name=%s", p.pid, p.info["name"])
        try:
            p.kill()
        except psutil.NoSuchProcess:
            logging.info("Process pid=%d already exited", p.pid)
    _, alive = psutil.wait_procs(targets, timeout=timeout)
    if alive:
        raise RuntimeError(f"Processes still alive after {timeout}s: {[p.pid for p in alive]}")
    logging.info("Killed %d process(es)", len(targets))


def replay(config: Config) -> None:
    logging.info("Hotkey triggered")
    kill_processes(config.process_name_keyword, config.kill_timeout_seconds)

    destination = config.save_target_dir / config.save_source_file.name
    shutil.copyfile(config.save_source_file, destination)
    logging.info("Copied %s -> %s", config.save_source_file, destination)

    process = subprocess.Popen(
        [str(config.executable)],
        cwd=str(config.executable.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    logging.info("Launched %s pid=%d", config.executable, process.pid)


def read_only_backup(config: Config) -> None:
    # 目标目录必须已经存在，文件复制用覆盖方式写入
    if not config.backup_source_file.is_file():
        raise FileNotFoundError(f"backup_source_file not found: {config.backup_source_file}")
    logging.info("Backup hotkey triggered")
    destination = config.backup_target_dir / config.backup_source_file.name
    shutil.copyfile(config.backup_source_file, destination)
    logging.info("Backup copied %s -> %s", config.backup_source_file, destination)


def run(raw: dict) -> None:
    config = load_config(raw)

    # 操作在主线程执行：hook 回调保持轻量，且异常可以直接终止进程
    # 两个热键各自向队列投递动作名，主线程阻塞取队列并执行对应操作
    events: queue.Queue[str] = queue.Queue()
    keyboard.add_hotkey(config.hotkey, lambda: events.put("replay"))
    keyboard.add_hotkey(config.backup_hotkey, lambda: events.put("backup"))
    logging.info("Listening hotkey=%s", config.hotkey)
    logging.info("Listening backup hotkey=%s", config.backup_hotkey)
    while True:
        action = events.get()
        if action == "replay":
            replay(config)
        else:
            read_only_backup(config)
