#!/usr/bin/env python3
# jetson_NX_monitor_freq_vdd.py
import re
import subprocess
import time

# ⚠️ 测试用；生产请用更安全方式或在 sudoers 配置免密
SUDO_PASSWORD = "123"

def sudo_check_output(cmd_list, timeout=5, allow_returncodes=(0,)):
    """
    运行 sudo -S CMD，返回 stdout 文本。
    allow_returncodes: 允许的返回码元组，默认只允许 0。
    """
    p = subprocess.run(
        ["sudo", "-S"] + cmd_list,
        input=(SUDO_PASSWORD + "\n").encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    out = p.stdout.decode(errors="ignore")
    err = p.stderr.decode(errors="ignore")
    if p.returncode not in allow_returncodes:
        raise RuntimeError(
            f"cmd failed: {' '.join(cmd_list)}\nstdout: {out}\nstderr: {err}"
        )
    return out

def read_voltage(path):
    """
    读取电压文件（mV），返回 int。
    """
    out = sudo_check_output(["cat", path], timeout=3)
    val = out.strip().splitlines()[-1].strip()
    if not val.isdigit():
        raise ValueError(f"Invalid voltage from {path}: '{val}'")
    return int(val)

def get_jetson_voltage():
    """
    获取电压。
    """
    stats = {"timestamp": time.time()}


    # 读取电压
    try:
        stats['voltage_in1 (mV)'] = read_voltage('/sys/class/hwmon/hwmon3/in1_input')
    except Exception as e:
        stats['voltage_in1 (mV)'] = None
        print(f"Error reading voltage in1: {e}")

    try:
        stats['voltage_in2 (mV)'] = read_voltage('/sys/class/hwmon/hwmon3/in2_input')
    except Exception as e:
        stats['voltage_in2 (mV)'] = None
        print(f"Error reading voltage in2: {e}")

    return stats

if __name__ == "__main__":
    print(get_jetson_voltage().get('voltage_in1 (mV)', 0))