#!/usr/bin/env python3
"""
G1 locomotion examples, get and set FSM ID to switch modes.

Usage:
  python setmode_action_fsm.py enp0s31f6
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

_G1_ROOT = Path(__file__).resolve().parents[1]
if str(_G1_ROOT) not in sys.path:
    sys.path.insert(0, str(_G1_ROOT))

from g1_loco_helpers import fsm_hint, get_fsm_id  # noqa: E402

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient


@dataclass
class TestOption:
    name: str
    id: int


option_list = [
    TestOption(name="Set mode: Zero Torque (CAUTION: robot relaxes all joints / falls instantly.)", id=0),
    TestOption(name="Set mode: Damping", id=1),
    TestOption(name="Test action: shake hand", id=2),
    TestOption(name="Get FSM ID", id=3),
    TestOption(name="Set FSM ID", id=4),
]


class UserInterface:
    def __init__(self):
        self.test_option_ = None

    def convert_to_int(self, input_str):
        try:
            return int(input_str)
        except ValueError:
            return None

    def terminal_handle(self):
        input_str = input("Enter id or name: \n")

        if input_str == "list":
            self.test_option_.name = None
            self.test_option_.id = None
            for option in option_list:
                print(f"{option.name}, id: {option.id}")
            return

        for option in option_list:
            if input_str == option.name or self.convert_to_int(input_str) == option.id:
                self.test_option_.name = option.name
                self.test_option_.id = option.id
                print(f"Test: {self.test_option_.name}, test_id: {self.test_option_.id}")
                return

        print("No matching test option found.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} networkInterface")
        sys.exit(-1)

    print("WARNING: Please ensure there are no obstacles around the robot while running this example.")
    input("Press Enter to continue...")

    ChannelFactoryInitialize(0, sys.argv[1])

    test_option = TestOption(name=None, id=None)
    user_interface = UserInterface()
    user_interface.test_option_ = test_option

    sport_client = LocoClient()
    sport_client.SetTimeout(10.0)
    sport_client.Init()

    print('Input "list" to list all test option ...')
    while True:
        user_interface.terminal_handle()

        print(f"Updated Test Option: Name = {test_option.name}, ID = {test_option.id}")

        if test_option.id == 0:
            sport_client.ZeroTorque()
        elif test_option.id == 1:
            sport_client.Damp()
        elif test_option.id == 2:
            sport_client.ShakeHand()
        elif test_option.id == 3:
            code, fsm_id = get_fsm_id(sport_client)
            if code != 0 or fsm_id is None:
                print(f"GetFsmId: FAIL (rpc code={code})")
                print("  → Fix network/DDS first (Lab 0), or run lab-02/fsm_readonly.py")
            else:
                print(f"GetFsmId: {fsm_id} — {fsm_hint(fsm_id)}")
        elif test_option.id == 4:
            print("0 = Zero Torque (CAUTION: robot relaxes all joints / falls instantly.)")
            print("1 = Damping")
            print("4 = Preparation")
            print("802 = Run")
            user_input = input("Enter FSM ID: ")
            fsm_id = int(user_input)
            sport_client.SetFsmId(fsm_id)

        time.sleep(1)
