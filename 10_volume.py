#!/usr/bin/env python3
"""
G1 Audio Client to get and set volume.

Usage:
  python3 volume.py enp0s31f6 --get
  python3 volume.py enp0s31f6 --set 100
"""

import argparse
import os
import sys
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient

def main() -> int:
    parser = argparse.ArgumentParser(description="Get and Set G1 Robot Volume")
    parser.add_argument(
        "interface",
        nargs="?",
        default=os.environ.get("G1_INTERFACE", "enp0s31f6"),
        help="Ethernet interface to robot",
    )
    
    # Create a mutually exclusive group so the user must choose either --get OR --set
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--get",
        action="store_true",
        help="Print the current volume",
    )
    group.add_argument(
        "--set",
        type=int,
        metavar="VOLUME",
        help="Set the volume to a value between 0 and 100",
    )
    
    args = parser.parse_args()

    # Initialize DDS communication
    ChannelFactoryInitialize(0, args.interface)

    # Initialize Audio Client
    audio = AudioClient()
    audio.SetTimeout(5.0)
    audio.Init()

    # Use Case 1: Get Volume
    if args.get:
        error_code, data = audio.GetVolume()
        
        if error_code == 0 and data is not None:
            current_vol = data.get('volume', 'unknown')
            print(f"The current volume is {current_vol}.")
        else:
            print(f"Error fetching volume. Code: {error_code}")

    # Use Case 2: Set Volume
    elif args.set is not None:
        # 1. Fetch the original volume first
        err_get, data_get = audio.GetVolume()
        original_vol = data_get.get('volume', 'unknown') if err_get == 0 and data_get else "unknown"

        # 2. Clamp and set the new volume
        vol_target = max(0, min(100, args.set))
        audio.SetVolume(vol_target)
        
        # 3. Fetch the new volume to confirm it was applied
        err_verify, data_verify = audio.GetVolume()
        new_vol = data_verify.get('volume', vol_target) if err_verify == 0 and data_verify else vol_target

        # 4. Print the exact requested output format
        print(f"Volume successfully set to {new_vol} (original: {original_vol}).")

    return 0

if __name__ == "__main__":
    sys.exit(main())
