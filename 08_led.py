#!/usr/bin/env python3
"""
G1 LED Light Strip Client.

Cycles the chest RGB LED through red, green, and blue sequences.

Usage:
  python3 led.py enp0s31f6
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_

WAIT_BETWEEN_LED_S = 1.5


def _init_dds(iface: str) -> None:
    if os.environ.get("CYCLONEDDS_URI"):
        print("Warning: CYCLONEDDS_URI is set; unset it for interface-only init.")
        ChannelFactoryInitialize(0)
    else:
        ChannelFactoryInitialize(0, iface)


def _wait_lowstate(timeout_s: float = 5.0) -> bool:
    got: list[int] = []

    def handler(msg: LowState_) -> None:
        got.append(int(msg.tick))

    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init(handler, 10)
    deadline = time.time() + timeout_s
    while time.time() < deadline and not got:
        time.sleep(0.05)
    return bool(got)


def _run_step(name: str, fn) -> int:
    print(f"\n--- {name} ---")
    result = fn()
    if isinstance(result, tuple):
        code = result[0]
        if len(result) > 1:
            print(f"  result: {result[1:]}")
    else:
        code = result
    if code is None:
        code = 0
    print(f"  return code: {code}")
    return int(code)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "interface",
        nargs="?",
        default=os.environ.get("G1_INTERFACE", "enp0s31f6"),
        help="Ethernet interface to robot",
    )
    args = parser.parse_args()

    if not os.environ.get("CYCLONEDDS_HOME"):
        print("ERROR: CYCLONEDDS_HOME is not set.")
        return 1

    print("WARNING: Robot chest RGB LEDs will change color.")
    _init_dds(args.interface)

    if not _wait_lowstate():
        print("FAIL: no rt/lowstate in 5s.")
        return 1
    print("DDS: rt/lowstate OK")

    # AudioClient is used here because LED control shares the physical hardware board
    audio = AudioClient()
    audio.SetTimeout(10.0)
    audio.Init()

    errors = 0

    errors += _run_step("LedControl (red)", lambda: audio.LedControl(255, 0, 0)) != 0
    time.sleep(WAIT_BETWEEN_LED_S)
    
    errors += _run_step("LedControl (green)", lambda: audio.LedControl(0, 255, 0)) != 0
    time.sleep(WAIT_BETWEEN_LED_S)
    
    errors += _run_step("LedControl (blue)", lambda: audio.LedControl(0, 0, 255)) != 0
    time.sleep(WAIT_BETWEEN_LED_S)
    
    # Optional: Turn off LEDs at the end (0, 0, 0)
    errors += _run_step("LedControl (off)", lambda: audio.LedControl(0, 0, 0)) != 0

    print()
    if errors:
        print(f"Done with {errors} non-zero step(s).")
        return 2
    print("Done. LED test sequence completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
