# HardGameFastSL

这个仓库提供一个 Windows 程序，用来给高难度游戏做快速 SL。SL 指结束当前对局，把存档恢复到事先留好的进度，再重新启动游戏，方便在同一段内容上反复练习。

程序启动后读取一份 JSON 配置。配置顶层只有一个 key，key 是游戏名称，value 是该游戏的配置。程序根据这个 key 选择对应的 SL 逻辑。一次运行只服务一个游戏，热键也只触发这一份配置里的流程。

目前支持的游戏名称是 `Sekiro`。

## Sekiro

只狼把进度写在存档文件里。游戏运行时会持续读写当前存档目录中的文件。快速重开时要先结束游戏进程，再替换存档。若在进程退出前复制，游戏仍可能把内存里的进度写回磁盘，覆盖刚放进去的存档。

按下配置里的热键之后，程序做三件事：

1. 按 `process_name_keyword` 在系统进程名里做不区分大小写的子串匹配，结束匹配到的进程，并等待它们退出。本程序自身以及它的父进程会被排除。
2. 把 `save_source_file` 复制到 `save_target_dir`。目标文件名与源文件名相同，目录里的同名存档会被覆盖。
3. 启动 `executable` 指向的 `sekiro.exe`，工作目录设为该可执行文件所在目录。

`save_source_file` 指向一份游戏不会自己改写的存档副本。`save_target_dir` 指向只狼实际读取的存档目录。常见的存档文件名是 `S0000.sl2`。

`kill_timeout_seconds` 是结束进程后最多等待的秒数。超时后程序直接报错并停止，存档保持原样。

## 配置

把 `config.json` 放在 `HardGameFastSL.exe` 同一目录，或者启动时用 `--config` 指定路径。日志写在配置文件同一目录，文件名是 `HardGameFastSL.log`。

```json
{
    "Sekiro": {
        "hotkey": "ctrl+r",
        "process_name_keyword": "Sekiro",
        "save_source_file": "<backup-save-file>",
        "save_target_dir": "<live-save-directory>",
        "executable": "<sekiro-install-directory>\\sekiro.exe",
        "kill_timeout_seconds": 10
    }
}
```

- `hotkey`：全局热键，写法与 Python `keyboard` 库的热键字符串一致。
- `process_name_keyword`：进程名关键字。只狼的进程名是 `sekiro.exe`，填写 `Sekiro` 即可匹配。
- `save_source_file`：要恢复的存档文件的完整路径。
- `save_target_dir`：游戏正在使用的存档目录的完整路径。
- `executable`：`sekiro.exe` 的完整路径。
- `kill_timeout_seconds`：结束进程后最多等待的秒数。

路径换成自己机器上的实际位置。顶层 key 必须正好是 `Sekiro`，且只能有这一个 key。字段必须与上面列出的一致。路径指向的文件和目录必须已经存在。任一条件不满足时，程序会直接退出。
