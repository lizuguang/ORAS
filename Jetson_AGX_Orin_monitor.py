#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jetson AGX Orin tegrastats 监测（持续进程版，自动处理 sudo 密码/免密）
- 仅启动一次 tegrastats，循环读取最新行
- 使用 stdbuf 让输出行缓冲
- 自动分支：
  1) 若配置 USE_SUDO=True 且 NOPASSWD 已设置，则用 sudo -n
  2) 若需要密码且提供了 SUDO_PASSWORD，则自动输入
  3) 若无需 sudo，则可直接 USE_SUDO=False
建议在 /etc/sudoers.d/tegrastats 配置免密：
  <your_user> ALL=(ALL) NOPASSWD: /usr/bin/tegrastats
"""

import re
import time
import atexit
import pexpect
import shutil

# ---------------- Config ----------------
INTERVAL_MS = 500                 # tegrastats 输出周期（毫秒）
USE_SUDO = True                   # 是否用 sudo
USE_STDBUF = True                 # 建议开启，保证行缓冲
USE_SUDO_PASSWORD = True         # 若需要密码改为 True 并填写 SUDO_PASSWORD
SUDO_PASSWORD = "password"             # ⚠️ 如启用密码模式，请改成你的密码

# 可指定绝对路径，或留空使用 PATH
SUDO_BIN = shutil.which("sudo") or "/usr/bin/sudo"
STDBUF_BIN = shutil.which("stdbuf") or "/usr/bin/stdbuf"
TEGRAS_BIN = shutil.which("tegrastats") or "/usr/bin/tegrastats"

# -------------- Globals ---------------
_child = None

def _build_cmd(no_password_mode: bool):
    """
    no_password_mode=True  -> sudo -n
    no_password_mode=False -> sudo（可提示密码）
    """
    cmd = []
    if USE_SUDO:
        if no_password_mode:
            cmd += [SUDO_BIN, "-n"]
        else:
            cmd += [SUDO_BIN]       # 不加 -n，允许提示密码
    if USE_STDBUF:
        cmd += [STDBUF_BIN, "-oL", "-eL"]
    cmd += [TEGRAS_BIN, "--interval", str(INTERVAL_MS)]
    return cmd

def _spawn_tegrastats():
    """尝试以免密模式启动；若失败且允许密码，则改为密码模式再启动。"""
    global _child

    # 优先尝试免密（sudo -n）如果配置了 USE_SUDO_PASSWORD=False 或希望先走免密
    try_password_mode = False

    for attempt in (1, 2):
        no_pw = (attempt == 1) and (not USE_SUDO_PASSWORD)  # 第一次：若未声明需要密码，则先试免密
        cmd = _build_cmd(no_password_mode=no_pw)

        _child = pexpect.spawn(
            cmd[0],
            cmd[1:],
            encoding="utf-8",
            timeout=5,
        )

        # 匹配首行可能的提示
        idx = _child.expect(
            [
                r"[Pp]assword",           # 需要密码提示
                r"password is required",  # sudo -n 时可能输出
                r"RAM", r"GR3D_FREQ", r"\d{2}-\d{2}-\d{4}",
                pexpect.EOF, pexpect.TIMEOUT
            ],
            timeout=5
        )

        if idx == 0 or idx == 1:
            # 遇到密码需求
            if USE_SUDO_PASSWORD:
                # 发送密码
                _child.sendline(SUDO_PASSWORD)
                # 再等待到数据字段
                _child.expect([r"RAM", r"GR3D_FREQ", r"\d{2}-\d{2}-\d{4}"], timeout=5)
                return
            else:
                # 未提供密码，结束本次并重试密码模式（第二轮）
                try_password_mode = True
                _child.terminate(force=True)
                _child = None
                continue
        elif idx in (2, 3, 4):
            # 成功进入数据输出
            return
        elif idx == 5:  # EOF
            raise RuntimeError("tegrastats EOF when starting")
        else:
            # TIMEOUT
            raise RuntimeError("tegrastats start timeout")

    # 如果走到这里，说明免密失败且未启用密码
    if try_password_mode and not USE_SUDO_PASSWORD:
        raise RuntimeError("需要 sudo 密码，但未配置 USE_SUDO_PASSWORD=True 和 SUDO_PASSWORD。")

def _start_tegrastats():
    global _child
    if _child is not None and _child.isalive():
        return
    _spawn_tegrastats()

def _stop_tegrastats():
    global _child
    if _child is not None:
        try:
            _child.terminate(force=True)
        except Exception:
            pass
    _child = None

atexit.register(_stop_tegrastats)

def _parse_line(line: str) -> dict:
    stats = {"timestamp": time.time()}

    m = re.search(r'GR3D_FREQ\s+\d+%@\[(\d+),(\d+)\]', line)
    if m:
        stats["gpu_freq_min (MHz)"] = int(m.group(1))
        stats["gpu_freq_max (MHz)"] = int(m.group(2))

    for label, key in [
        ("GPU", "temp_GPU (°C)"),
        ("CPU", "temp_CPU (°C)"),
        ("SOC0", "temp_SOC0 (°C)"),
        ("SOC1", "temp_SOC1 (°C)"),
        ("SOC2", "temp_SOC2 (°C)"),
        ("Tboard", "temp_Tboard (°C)"),
        ("Tdiode", "temp_Tdiode (°C)"),
    ]:
        m = re.search(fr'{label}@([-\d.]+)C', line)
        if m:
            stats[key] = float(m.group(1))

    m = re.search(r'VDD_GPU_SOC\s+(\d+)mW', line)
    if m: stats["power_VDD_GPU_SOC (mW)"] = int(m.group(1))
    m = re.search(r'VDD_CPU_CV\s+(\d+)mW', line)
    if m: stats["power_VDD_CPU_CV (mW)"] = int(m.group(1))
    m = re.search(r'VIN_SYS_5V0\s+(\d+)mW', line)
    if m: stats["power_VIN_SYS_5V0 (mW)"] = int(m.group(1))

    return stats

def get_jetson_stats():
    """
    获取最新一行 tegrastats 数据。
    若进程异常退出，会自动重启。
    """
    global _child
    _start_tegrastats()

    try:
        line = _child.readline().strip()
        if not line:
            raise RuntimeError("Empty line from tegrastats")
        return _parse_line(line)
    except Exception:
        # 出错重启
        _stop_tegrastats()
        _start_tegrastats()
        line = _child.readline().strip()
        if not line:
            raise RuntimeError("Failed to read tegrastats after restart")
        return _parse_line(line)

if __name__ == "__main__":
    for _ in range(10):
        print(get_jetson_stats())
        time.sleep(1)