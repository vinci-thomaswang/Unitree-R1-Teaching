#!/usr/bin/env python3
"""
G1 Text To Speech (TTS) from input text (Chinese/English).

Usage:
  python3 tts.py enp0s31f6 --lang en --text "Hello, how are you today?"
  python3 tts.py enp0s31f6 --lang ch --text "你好，今天怎么样？"
"""

import time
import sys
import argparse
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Unitree G1 TTS Script")
    
    # Positional argument for the network interface
    parser.add_argument("interface", type=str, help="Network interface (e.g., enp0s31f6)")
    
    # Optional arguments with specific constraints
    parser.add_argument("--lang", type=str, choices=["ch", "en"], required=True, 
                        help="Language choice: 'ch' for Chinese, 'en' for English")
    parser.add_argument("--text", type=str, required=True, 
                        help="The text string you want the robot to speak")

    args = parser.parse_args()

    # Map the --lang choice to the corresponding SPEAKER_ID
    # 0: Chinese, 1: English
    speaker_id = 0 if args.lang == "ch" else 1

    # Initialize Channel Factory with the network interface
    ChannelFactoryInitialize(0, args.interface)

    # Initialize clients
    audio_client = AudioClient()  
    audio_client.SetTimeout(10.0)
    audio_client.Init()

    sport_client = LocoClient()  
    sport_client.SetTimeout(10.0)
    sport_client.Init()

    # Robot action
    sport_client.WaveHand()

    # Execute TTS with the user-defined text and language ID
    print(f"Speaking ({args.lang}): {args.text}")
    audio_client.TtsMaker(args.text, speaker_id)
    
    # Give it some time to finish speaking before the script exits
    time.sleep(5)
