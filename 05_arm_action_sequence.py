#!/usr/bin/env python3
"""
Scripted high-level arm actions via G1ArmActionClient ("arm" RPC).

  --show-map      Print static action_map from SDK (no robot, no DDS).
  --dry-run       Readiness only
  --list-actions  Call GetActionList() on the robot (needs DDS + G1).
  default         Run a comma-separated --sequence of ExecuteAction calls.
  --pause         Pause duration (seconds) between each action.
  --sequence      Set the sequence: comma-separated ExecuteAction calls.

Usage:
  python3 arm_action_sequence.py --show-map
  python3 arm_action_sequence.py enp0s31f6 --dry-run
  python3 arm_action_sequence.py enp0s31f6 --list-actions
  python3 arm_action_sequence.py enp0s31f6
  python3 arm_action_sequence.py enp0s31f6 --pause 1
  python3 arm_action_sequence.py enp0s31f6 --sequence "heart,release arm,two-hand kiss,release arm,reject,release arm" --pause 0.5
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
from unitree_sdk2py.g1.arm.g1_arm_action_client import G1ArmActionClient, action_map
from unitree_sdk2py.g1.loco.g1_loco_api import ROBOT_API_ID_LOCO_GET_FSM_ID
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_


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


def _get_fsm_id(loco: LocoClient) -> int | None:
    code, raw = loco._Call(ROBOT_API_ID_LOCO_GET_FSM_ID, "{}")
    if code != 0 or not raw:
        return None
    data = json.loads(raw).get("data")
    if isinstance(data, float) and data.is_integer():
        return int(data)
    return int(data) if isinstance(data, int) else None


def check_ready(loco: LocoClient) -> tuple[bool, str]:
    if not _wait_lowstate():
        return False, "no rt/lowstate"

    msc = MotionSwitcherClient()
    msc.SetTimeout(10.0)
    msc.Init()
    code, result = msc.CheckMode()
    if code != 0:
        return False, f"CheckMode failed code={code}"
    name = (result or {}).get("name", "")
    if name != "ai":
        return False, f"CheckMode name={name!r} (expected 'ai')"

    fsm = _get_fsm_id(loco)
    if fsm is None:
        return False, "could not read FSM id"
    if fsm == 1:
        return False, "FSM=1 (damp)"
    return True, f"lowstate OK, CheckMode ai, FSM={fsm}"


def _parse_sequence(spec: str) -> list[str]:
    names = [p.strip() for p in spec.split(",") if p.strip()]
    bad = [n for n in names if n not in action_map]
    if bad:
        raise ValueError(
            "Unknown action name(s): "
            + ", ".join(repr(b) for b in bad)
            + ". Use --show-map for valid keys."
        )
    return names


def _print_action_map() -> None:
    print("Static action_map from unitree_sdk2py (ExecuteAction id):")
    print()
    for name in sorted(action_map.keys(), key=lambda k: (action_map[k], k)):
        print(f"  {action_map[name]:3d}  {name}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "interface",
        nargs="?",
        default=os.environ.get("G1_INTERFACE", "enp0s31f6"),
        help="Ethernet interface (not used with --show-map)",
    )
    parser.add_argument(
        "--show-map",
        action="store_true",
        help="Print SDK action_map and exit (no robot)",
    )
    parser.add_argument(
        "--list-actions",
        action="store_true",
        help="RPC GetActionList() only — text output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Readiness check only; no arm RPC",
    )
    parser.add_argument(
        "--sequence",
        default="high wave,clap,release arm",
        metavar="NAMES",
        help='Comma-separated names from action_map (default: "high wave,clap,release arm")',
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=3.0,
        metavar="SEC",
        help="Sleep SEC after each ExecuteAction except the last (default: 3)",
    )
    args = parser.parse_args()

    if args.show_map:
        _print_action_map()
        return 0

    if not os.environ.get("CYCLONEDDS_HOME"):
        print("ERROR: CYCLONEDDS_HOME is not set.")
        return 1

    print("WARNING: Ensure clear space around the robot.")
    print(f"Interface: {args.interface}")
    _init_dds(args.interface)

    loco = LocoClient()
    loco.SetTimeout(10.0)
    loco.Init()

    ok, detail = check_ready(loco)
    print(f"\nReadiness: {'PASS' if ok else 'FAIL'} — {detail}")
    if not ok:
        return 1

    arm = G1ArmActionClient()
    arm.SetTimeout(10.0)
    arm.Init()

    if args.list_actions:
        print("\n--- GetActionList() ---")
        code, data = arm.GetActionList()
        print(f"  return code: {code}")
        if code == 0 and data is not None:
            print(json.dumps(data, indent=2))
        else:
            print("  (no data — firmware may not expose this API; use --show-map)")
        return 0 if code == 0 else 3

    if args.dry_run:
        print("Dry run complete (no ExecuteAction sent).")
        return 0

    try:
        steps = _parse_sequence(args.sequence)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    print(f"\nSequence ({len(steps)} step(s)): {steps}")
    errors = 0
    for i, name in enumerate(steps):
        aid = action_map[name]
        print(f"\n--- ExecuteAction({name!r} id={aid}) ---")
        code = arm.ExecuteAction(aid)
        print(f"  return code: {code}")
        if code != 0:
            errors += 1
        if i < len(steps) - 1 and args.pause > 0:
            time.sleep(args.pause)

    print()
    if errors:
        print(f"Done with {errors} non-zero step(s). Watch robot and logs.")
        return 2
    print("Done. Sequence completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
