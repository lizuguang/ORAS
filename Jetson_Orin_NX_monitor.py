#!/usr/bin/env python3
import re
import pexpect
import time

def get_jetson_stats():
    """
    获取 Jetson NX 的 GPU 频率、GPU 温度、CPU/GPU/SOC/总线功耗
    返回: dict
    {
        "gpu_freq_min (MHz)": int,
        "temp_GPU (°C)": float,
        "power_VDD_CPU_GPU_CV (mW)": int,
        "power_VDD_IN (mW)": int,
        "power_VDD_SOC (mW)": int
    }
    """
    child = pexpect.spawn("sudo tegrastats --interval 500", timeout=5)
    
    # 兼容 sudo 是否需要密码
    i = child.expect([r"\[", r"[Pp]assword", pexpect.EOF, pexpect.TIMEOUT], timeout=5)

    if i == 1:  # 要求输入密码
        child.sendline("123")  # ⚠️ 这里建议换成安全方式
        child.expect(r"\[", timeout=5)

    # 读取一行输出
    line = child.readline().decode("utf-8", errors="ignore")
    child.terminate(force=True)

    stats = {}
    stats["timestamp"] = time.time()

    # GPU freq
    gpu_match = re.search(r'GR3D_FREQ\s+\d+%@\[(\d+),(\d+)\]', line)
    if gpu_match:
        stats['gpu_freq_min (MHz)'] = int(gpu_match.group(1))

    # GPU temp
    temp_match = re.search(r'GPU@([-\d.]+)C', line)
    if temp_match:
        stats['temp_GPU (°C)'] = float(temp_match.group(1))

    # Power: CPU+GPU+CV
    power_match = re.search(r'VDD_CPU_GPU_CV\s+(\d+)mW', line)
    if power_match:
        stats['power_VDD_CPU_GPU_CV (mW)'] = int(power_match.group(1))

    # Power: VDD_IN (整机功耗)
    vdd_in_match = re.search(r'VDD_IN\s+(\d+)mW', line)
    if vdd_in_match:
        stats['power_VDD_IN (mW)'] = int(vdd_in_match.group(1))

    # Power: VDD_SOC
    vdd_soc_match = re.search(r'VDD_SOC\s+(\d+)mW', line)
    if vdd_soc_match:
        stats['power_VDD_SOC (mW)'] = int(vdd_soc_match.group(1))

    return stats


if __name__ == "__main__":
    result = get_jetson_stats()
    print("Jetson NX Stats:", result)
