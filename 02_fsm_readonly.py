#!/usr/bin/env python3
"""
Read G1 locomotion FSM and motion mode via RPC (no motion commands).

Usage:
  python3 fsm_readonly.py enp0s31f6
  python3 fsm_readonly.py enp0s31f6 --watch 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import (
    MotionSwitcherClient,
)
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.g1.loco.g1_loco_api import (
    ROBOT_API_ID_LOCO_GET_BALANCE_MODE,
    ROBOT_API_ID_LOCO_GET_FSM_ID,
    ROBOT_API_ID_LOCO_GET_FSM_MODE,
    ROBOT_API_ID_LOCO_GET_STAND_HEIGHT,
    ROBOT_API_ID_LOCO_GET_SWING_HEIGHT,
)
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_


# Known FSM ids from unitree_sdk2py.g1.loco.g1_loco_client convenience methods
FSM_HINTS: dict[int, str] = {
    0: "zero torque (ZeroTorque)",
    1: "damp (Damp) — high-level wave/walk blocked",
    3: "sit (Sit)",
    500: "start (Start)",
    702: "lie to stand up (Lie2StandUp)",
    706: "squat / stand transition (Squat2StandUp, StandUp2Squat)",
}


def _init_dds(iface: str) -> None:
    if os.environ.get("CYCLONEDDS_URI"):
        print("Warning: CYCLONEDDS_URI is set; unset it for interface-only init.")
        ChannelFactoryInitialize(0)
    else:
        ChannelFactoryInitialize(0, iface)


def _loco_get(client: LocoClient, api_id: int) -> tuple[int, object | None]:
    code, raw = client._Call(api_id, "{}")
    if code != 0 or not raw:
        return code, None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return code, raw
    return code, payload.get("data", payload)


def _fsm_hint(fsm_id: int | None) -> str:
    if fsm_id is None:
        return "unknown"
    return FSM_HINTS.get(fsm_id, "see Unitree sport docs / observe during operation")


def _check_lowstate(timeout_s: float = 5.0) -> tuple[bool, int | None]:
    got: list[int] = []

    def handler(msg: LowState_) -> None:
        got.append(int(msg.tick))

    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init(handler, 10)
    deadline = time.time() + timeout_s
    while time.time() < deadline and not got:
        time.sleep(0.05)
    return bool(got), (got[0] if got else None)


def _read_report() -> dict[str, object]:
    loco = LocoClient()
    loco.SetTimeout(10.0)
    loco.Init()

    msc = MotionSwitcherClient()
    msc.SetTimeout(10.0)
    msc.Init()

    code_mode, check_mode = msc.CheckMode()

    reads: dict[str, tuple[int, object | None]] = {
        "fsm_id": _loco_get(loco, ROBOT_API_ID_LOCO_GET_FSM_ID),
        "fsm_mode": _loco_get(loco, ROBOT_API_ID_LOCO_GET_FSM_MODE),
        "balance_mode": _loco_get(loco, ROBOT_API_ID_LOCO_GET_BALANCE_MODE),
        "stand_height": _loco_get(loco, ROBOT_API_ID_LOCO_GET_STAND_HEIGHT),
        "swing_height": _loco_get(loco, ROBOT_API_ID_LOCO_GET_SWING_HEIGHT),
    }

    fsm_id = reads["fsm_id"][1] if reads["fsm_id"][0] == 0 else None
    if isinstance(fsm_id, float) and fsm_id.is_integer():
        fsm_id = int(fsm_id)

    mode_name = ""
    if code_mode == 0 and isinstance(check_mode, dict):
        mode_name = str(check_mode.get("name", ""))

    return {
        "check_mode_code": code_mode,
        "check_mode": check_mode,
        "mode_name": mode_name,
        "reads": reads,
        "fsm_id": fsm_id if isinstance(fsm_id, int) else None,
    }


def _print_report(
    iface: str,
    lowstate_ok: bool,
    lowstate_tick: int | None,
    report: dict[str, object],
) -> int:
    print(f"Interface: {iface}")
    print()
    print("[DDS topic]")
    if lowstate_ok:
        print(f"  rt/lowstate: OK (tick={lowstate_tick})")
    else:
        print("  rt/lowstate: FAIL (no messages in 5s)")

    print()
    print("[Motion switcher RPC]")
    code = report["check_mode_code"]
    check_mode = report["check_mode"]
    mode_name = report["mode_name"]
    if code != 0:
        print(f"  CheckMode: FAIL (code={code})")
    else:
        ai_ok = mode_name == "ai"
        mark = "OK" if ai_ok else "WARN"
        print(f"  CheckMode: {mark}  name={mode_name!r}  full={check_mode}")

    print()
    print('[LocoClient RPC — service "sport"]')
    labels = {
        "fsm_id": "FSM id (7001)",
        "fsm_mode": "FSM mode (7002)",
        "balance_mode": "balance mode (7003)",
        "stand_height": "stand height (7005)",
        "swing_height": "swing height (7004)",
    }
    reads = report["reads"]
    for key, label in labels.items():
        api_code, value = reads[key]
        if api_code != 0:
            extra = " (optional on some firmware)" if api_code == 7301 else ""
            print(f"  {label}: read failed (code={api_code}){extra}")
        else:
            print(f"  {label}: {value}")

    fsm_id = report["fsm_id"]
    print()
    if fsm_id is not None:
        print(f"FSM summary: id={fsm_id} — {_fsm_hint(fsm_id)}")
    else:
        print("FSM summary: could not read FSM id")

    print()
    ready_motion = (
        lowstate_ok
        and code == 0
        and mode_name == "ai"
        and fsm_id is not None
        and fsm_id != 1
    )
    if ready_motion:
        print("Readiness: PASS — OK for high-level LocoClient motions")
        return 0
    if lowstate_ok and fsm_id == 1:
        print("Readiness: PARTIAL — DDS OK but FSM=1 (damp)")
        print("  Recover: stand robot (feet on floor); remote L1+UP if paired.")
        return 2
    if lowstate_ok and mode_name != "ai":
        print(f"Readiness: PARTIAL — DDS OK but CheckMode name is {mode_name!r}, not 'ai'")
        return 2
    print("Readiness: FAIL — fix network/DDS (Lab 0) before Lab 3")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "interface",
        nargs="?",
        default=os.environ.get("G1_INTERFACE", "enp0s31f6"),
        help="Ethernet interface to robot",
    )
    parser.add_argument(
        "--watch",
        type=float,
        metavar="SEC",
        help="Re-read RPC state every 2s for SEC seconds (read-only)",
    )
    args = parser.parse_args()

    if not os.environ.get("CYCLONEDDS_HOME"):
        print("ERROR: CYCLONEDDS_HOME is not set.")
        return 1

    _init_dds(args.interface)

    def once() -> int:
        lowstate_ok, tick = _check_lowstate()
        report = _read_report()
        return _print_report(args.interface, lowstate_ok, tick, report)

    if not args.watch:
        return once()

    end = time.time() + args.watch
    last_exit = 0
    while time.time() < end:
        print("=" * 60)
        last_exit = once()
        print()
        time.sleep(2.0)
    return last_exit


if __name__ == "__main__":
    sys.exit(main())
