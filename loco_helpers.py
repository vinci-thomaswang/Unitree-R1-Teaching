"""Shared G1 LocoClient RPC helpers for Day 5 labs."""

from __future__ import annotations

import json

from unitree_sdk2py.g1.loco.g1_loco_api import ROBOT_API_ID_LOCO_GET_FSM_ID
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient

FSM_HINTS: dict[int, str] = {
    0: "zero torque (ZeroTorque)",
    1: "damp (Damp) — high-level wave/walk blocked",
    3: "sit (Sit)",
    500: "start (Start)",
    702: "lie to stand up (Lie2StandUp)",
    706: "squat / stand transition (Squat2StandUp, StandUp2Squat)",
}


def loco_rpc_get(client: LocoClient, api_id: int) -> tuple[int, object | None]:
    """Call a registered LocoClient GET RPC; return (code, data field)."""
    code, raw = client._Call(api_id, "{}")
    if code != 0 or not raw:
        return code, None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return code, raw
    return code, payload.get("data", payload)


def get_fsm_id(client: LocoClient) -> tuple[int, int | None]:
    """
    Read locomotion FSM id via sport RPC 7001.

    G1 LocoClient exposes SetFsmId() but not GetFsmId() (H2 has that wrapper).
    Returns (rpc_code, fsm_id). fsm_id is None when the read failed.
    """
    code, data = loco_rpc_get(client, ROBOT_API_ID_LOCO_GET_FSM_ID)
    if isinstance(data, float) and data.is_integer():
        return code, int(data)
    if isinstance(data, int):
        return code, data
    return code, None


def fsm_hint(fsm_id: int | None) -> str:
    if fsm_id is None:
        return "unknown"
    return FSM_HINTS.get(fsm_id, "see Unitree sport docs / observe during operation")
