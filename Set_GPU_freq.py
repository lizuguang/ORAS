#!/usr/bin/env python3
# set_gpu_max_freq.py
"""
Set Jetson Orin NX GPU max frequency reliably (simplified version).

- Writes only to the max_freq sysfs node
- Uses `sudo -S sh -c 'echo <hz> > <path>'` (root shell redirection)
- Supplies sudo password via stdin (⚠️ insecure)
- Does NOT read or verify cur_freq
"""

import os
import subprocess
import sys
import time
from typing import Optional

# ---------------- CONFIG ----------------
SUDO_PASS_HARDCODED = "password"  # ⚠️ Insecure: hardcoded password
TARGET_FREQ_MHZ = 502        # 目标 GPU 频率（MHz）
MAX_FREQ_PATH = "/sys/devices/17000000.ga10b/devfreq/17000000.ga10b/max_freq"
# ----------------------------------------

def _mhz_to_hz_str(freq_mhz: int) -> str:
    return str(int(freq_mhz) * 1_000_000)

def set_gpu_max_freq(freq_mhz: int,
                     timeout: float = 8.0,
                     verbose: bool = False) -> bool:
    """
    Set GPU max frequency without verifying cur_freq.

    Returns:
        success: bool
    """
    hz_str = _mhz_to_hz_str(freq_mhz)

    cmd = ["sudo", "-S", "sh", "-c", f"echo {hz_str} > {MAX_FREQ_PATH}"]
    if verbose:
        print("[DEBUG] running:", " ".join(cmd))

    try:
        proc = subprocess.run(cmd, input=SUDO_PASS_HARDCODED + "\n", text=True,
                              capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        if verbose:
            print("[ERROR] subprocess timed out")
        return False
    except Exception as e:
        if verbose:
            print("[ERROR] subprocess exception:", e)
        return False

    if proc.returncode != 0:
        if verbose:
            print(f"[FAIL] returncode={proc.returncode}")
            if proc.stderr:
                print("stderr:", proc.stderr.strip())
            if proc.stdout:
                print("stdout:", proc.stdout.strip())
        return False

    # Short delay for driver update
    time.sleep(0.2)

    if verbose:
        print(f"[OK] GPU max frequency set to {freq_mhz} MHz")
    return True


# ---------------- MAIN ----------------
if __name__ == "__main__":
    print(f"[INFO] Target GPU freq = {TARGET_FREQ_MHZ} MHz")
    success = set_gpu_max_freq(TARGET_FREQ_MHZ)
    if success:
        print(f"[SUCCESS] GPU max freq set to {TARGET_FREQ_MHZ} MHz")
    else:
        print(f"[FAIL] Could not set GPU max freq to {TARGET_FREQ_MHZ} MHz")

    # If running as a script, exit with status
    if not hasattr(sys, "ps1"):
        sys.exit(0 if success else 2)