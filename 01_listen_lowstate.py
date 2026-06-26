#!/usr/bin/env python3
"""
Subscribe to G1 rt/lowstate and print robot state (no motion commands).

Usage:
  python3 listen_lowstate.py enp0s31f6
  python3 listen_lowstate.py enp0s31f6 --duration 5
  python3 listen_lowstate.py enp0s31f6 --once
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_


def _init_dds(iface: str) -> None:
    if os.environ.get("CYCLONEDDS_URI"):
        print("Warning: CYCLONEDDS_URI is set; unset it for interface-only init.")
        ChannelFactoryInitialize(0)
    else:
        ChannelFactoryInitialize(0, iface)


def _format_lowstate(msg: LowState_, count: int) -> str:
    imu = msg.imu_state
    n_motors = len(msg.motor_state) if msg.motor_state else 0
    return (
        f"[{count:4d}] tick={msg.tick} "
        f"mode_pr={msg.mode_pr} mode_machine={msg.mode_machine} "
        f"imu_rpy=({imu.rpy[0]:.3f},{imu.rpy[1]:.3f},{imu.rpy[2]:.3f}) "
        f"motors={n_motors} version={list(msg.version)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "interface",
        nargs="?",
        default=os.environ.get("G1_INTERFACE", "enp0s31f6"),
        help="Ethernet interface to robot (e.g. en6 on macOS)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Seconds to listen after first message (default: 10)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print first message and exit",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=2.0,
        help="Max print rate in Hz after first message (default: 2)",
    )
    args = parser.parse_args()

    if not os.environ.get("CYCLONEDDS_HOME"):
        print("ERROR: CYCLONEDDS_HOME is not set.")
        return 1

    print(f"Interface: {args.interface}")
    _init_dds(args.interface)

    count = 0
    first_at: float | None = None
    last_print = 0.0
    min_interval = 1.0 / args.rate if args.rate > 0 else 0.0

    def on_lowstate(msg: LowState_) -> None:
        nonlocal count, first_at, last_print
        count += 1
        now = time.time()
        if first_at is None:
            first_at = now
            print("First rt/lowstate received:")
            print("  " + _format_lowstate(msg, count))
            if args.once:
                return
        if args.once:
            return
        if now - last_print >= min_interval:
            last_print = now
            print("  " + _format_lowstate(msg, count))

    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init(on_lowstate, 10)

    print('Subscribed to "rt/lowstate" (LowState_, unitree_hg). Waiting...')
    deadline = time.time() + 8.0
    while time.time() < deadline and count == 0:
        time.sleep(0.05)

    if count == 0:
        print(
            "FAIL: no messages in 8s. Run checks: "
            "python g1_connection_check.py --interface",
            args.interface,
        )
        return 1

    if args.once:
        print(f"Done. ({count} message(s) received)")
        return 0

    end = time.time() + args.duration
    while time.time() < end:
        time.sleep(0.05)

    elapsed = time.time() - (first_at or time.time())
    hz = count / elapsed if elapsed > 0 else 0.0
    print(f"Done. {count} messages in {elapsed:.1f}s (~{hz:.0f} Hz)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
