# Unitree R1 Robotics Course

Welcome! This folder contains Python scripts that let your computer talk to the Unitree R1 robot over the network. Each script builds on the last — from **listening** to what the robot reports, to **moving** its arms, to **lights and sound**.

Run most scripts like this (replace `enp0s31f6` with your own network interface name):

```bash
python3 01_listen_lowstate.py enp0s31f6
```

> **Before you start:** Make sure `CYCLONEDDS_HOME` is set up on your machine, and always keep clear space around the robot when running motion or audio scripts.

---

## How the scripts fit together

| Script | Topic |
|--------|--------|
| `01_listen_lowstate.py` | Hear what the robot is reporting |
| `02_fsm_readonly.py` | Check if the robot is ready to move |
| `03_setmode_action_fsm.py` | Change robot modes and try simple actions |
| `04_arm_action_example.py` | Try individual arm gestures |
| `05_arm_action_sequence.py` | Chain arm gestures into a routine |
| `08_led.py` | Control the chest LED colours |
| `09_audio.py` | Play a `.wav` sound file |
| `10_volume.py` | Read and change speaker volume |
| `11_tts.py` | Make the robot speak text |

---

## 01 — Listen to the robot (`01_listen_lowstate.py`)

### What it does

This is your first “conversation” with the robot. The script **listens** to a live data feed called `rt/lowstate` and prints a short summary on screen — things like how the robot is tilted (IMU) and how many motors are reporting. It does **not** tell the robot to move; it only watches.

Think of it like checking a fitness tracker: you read the numbers, you don’t control the person.

### Key ideas in the code

**Connecting to the robot**

```python
ChannelFactoryInitialize(0, iface)
```

This line opens the communication channel on your chosen network interface (the cable/Wi‑Fi adapter that talks to the robot).

**Subscribing to updates**

```python
sub = ChannelSubscriber("rt/lowstate", LowState_)
sub.Init(on_lowstate, 10)
```

A *subscriber* is like signing up for notifications. Every time the robot sends a new `LowState` message, your `on_lowstate` function runs.

**The callback function**

```python
def on_lowstate(msg: LowState_) -> None:
    ...
    print("  " + _format_lowstate(msg, count))
```

Whenever a message arrives, this function formats the interesting fields (tick counter, IMU angles, motor count) and prints them. The `--rate` option limits how often it prints so your screen doesn’t scroll too fast.

**Waiting for the first message**

```python
while time.time() < deadline and count == 0:
    time.sleep(0.05)
```

The script waits up to 8 seconds for data. If nothing arrives, it tells you the connection probably isn’t working yet.

---

## 02 — Read robot status (`02_fsm_readonly.py`)

### What it does

Before you ask the robot to walk or wave, you need to know its **state**. This script asks the robot (read-only — no movement commands):

- Is the data feed (`rt/lowstate`) working?
- What **mode** is the motion system in?
- What is the **FSM id**? (FSM = Finite State Machine — basically “which behaviour mode is the robot in right now?”)

At the end it prints **Readiness: PASS** or **FAIL** so you know if it’s safe to run motion scripts later.

### Key ideas in the code

**FSM hints — translating numbers to English**

```python
FSM_HINTS: dict[int, str] = {
    0: "zero torque (ZeroTorque)",
    1: "damp (Damp) — high-level wave/walk blocked",
    ...
}
```

Robot internals use numeric codes. This dictionary helps you understand what each number means when it’s printed.

**Two ways to ask the robot questions**

1. **DDS topic** — passive listening (same idea as script 01):

```python
sub = ChannelSubscriber("rt/lowstate", LowState_)
```

2. **RPC calls** — active questions you send and get answers back:

```python
loco = LocoClient()
loco.Init()
...
"fsm_id": _loco_get(loco, ROBOT_API_ID_LOCO_GET_FSM_ID),
```

`LocoClient` talks to the robot’s “sport” service. Each `ROBOT_API_ID_...` is a different question (FSM id, balance mode, stand height, etc.).

**Readiness check**

```python
ready_motion = (
    lowstate_ok
    and code == 0
    and mode_name == "ai"
    and fsm_id is not None
    and fsm_id != 1
)
```

All of these must be true before the script says you’re ready for high-level motions. If FSM is `1` (damp), the robot is in a safe-but-frozen state and won’t do wave/walk commands until you recover (e.g. stand it up properly).

---

## 03 — Change modes and try actions (`03_setmode_action_fsm.py`)

### What it does

This script adds **control**. Through a simple text menu you can:

- Put the robot in **zero torque** or **damping** (be careful — zero torque lets joints go limp!)
- Make it **shake hands**
- **Read** or **set** the FSM id to switch behaviour modes

Type `list` to see all options, then enter a name or number.

### Key ideas in the code

**Menu options as data**

```python
option_list = [
    TestOption(name="Set mode: Zero Torque (...)", id=0),
    TestOption(name="Set mode: Damping", id=1),
    ...
]
```

Each menu item is a small `TestOption` object with a human-readable `name` and an `id` used in the code below.

**Matching user input**

```python
for option in option_list:
    if input_str == option.name or self.convert_to_int(input_str) == option.id:
        ...
```

You can type either the full name or just the number — the loop finds the right choice.

**Sending commands based on choice**

```python
if test_option.id == 0:
    sport_client.ZeroTorque()
elif test_option.id == 1:
    sport_client.Damp()
elif test_option.id == 2:
    sport_client.ShakeHand()
elif test_option.id == 3:
    code, fsm_id = get_fsm_id(sport_client)
```

`LocoClient` methods are the actual orders sent to the robot. `get_fsm_id` (from `loco_helpers.py`) is a helper that reads the current FSM number.

**Safety pause**

```python
input("Press Enter to continue...")
```

The script stops and waits for you before connecting — a reminder to clear the area around the robot.

---

## 04 — Arm gestures one at a time (`04_arm_action_example.py`)

### What it does

Now we focus on the **arms**. Pick from a menu of built-in gestures: wave, clap, heart, hug, high five, and more. After some gestures the script automatically sends **release arm** so the arms return to a neutral pose.

### Key ideas in the code

**The action map**

```python
from unitree_sdk2py.g1.arm.g1_arm_action_client import action_map
...
armAction_client.ExecuteAction(action_map.get("shake hand"))
```

`action_map` is a dictionary that converts friendly names like `"shake hand"` into numeric action IDs the robot understands. You don’t need to memorise the numbers — use the string keys.

**Arm client setup**

```python
armAction_client = G1ArmActionClient()
armAction_client.SetTimeout(10.0)
armAction_client.Init()
```

Same pattern as `LocoClient`: create client, set how long to wait for a reply, then `Init()` to connect.

**Gesture + release pattern**

```python
armAction_client.ExecuteAction(action_map.get("shake hand"))
time.sleep(2)
armAction_client.ExecuteAction(action_map.get("release arm"))
```

Many poses are held for 2 seconds, then released. Gestures like `high wave` or `clap` may loop until you choose something else — check the `if/elif` blocks to see which ones auto-release.

---

## 05 — Arm gesture sequence (`05_arm_action_sequence.py`)

### What it does

Instead of picking one gesture at a time, this script runs a **choreographed sequence** — for example: high wave → clap → release arm. You can customise the list and pause between steps from the command line.

It also has helper modes: show all action names, check if the robot is ready, or list actions from the robot itself.

### Key ideas in the code

**Parsing your sequence string**

```python
def _parse_sequence(spec: str) -> list[str]:
    names = [p.strip() for p in spec.split(",") if p.strip()]
    bad = [n for n in names if n not in action_map]
```

You pass something like `"heart,release arm,clap"`. The function splits on commas and checks every name exists in `action_map` before running anything.

**Readiness before moving**

```python
ok, detail = check_ready(loco)
if not ok:
    return 1
```

Reuses the same ideas as script 02: lowstate must work, mode must be `"ai"`, and FSM must not be damp (`1`).

**Running the sequence in a loop**

```python
for i, name in enumerate(steps):
    aid = action_map[name]
    code = arm.ExecuteAction(aid)
    if i < len(steps) - 1 and args.pause > 0:
        time.sleep(args.pause)
```

Each step looks up the action id, sends it, waits `--pause` seconds, then continues. The last step doesn’t sleep afterward.

**Try without the robot**

```bash
python3 05_arm_action_sequence.py --show-map
```

Prints all valid gesture names from the SDK — useful when planning your sequence offline.

---

## 08 — Chest LED colours (`08_led.py`)

### What it does

The robot has RGB LEDs on its chest. This script cycles through **red → green → blue → off**, pausing briefly between each colour so you can see the change.

### Key ideas in the code

**LED control through AudioClient**

```python
audio = AudioClient()
audio.Init()
...
audio.LedControl(255, 0, 0)   # red
audio.LedControl(0, 255, 0)   # green
audio.LedControl(0, 0, 255)   # blue
audio.LedControl(0, 0, 0)     # off
```

Surprisingly, LEDs are controlled by `AudioClient` because they share hardware on the same board. Each `LedControl(r, g, b)` call takes three numbers from 0–255 for red, green, and blue.

**Checking connection first**

```python
if not _wait_lowstate():
    print("FAIL: no rt/lowstate in 5s.")
    return 1
```

Same pattern as other scripts: confirm the data feed works before sending commands.

---

## 09 — Play a sound file (`09_audio.py`)

### What it does

Plays a `.wav` audio file through the robot’s speakers. The file must be **16 kHz, mono** (one channel) — the script checks this and refuses unsupported formats.

### Key ideas in the code

**Reading the WAV file**

```python
pcm_list, sample_rate, num_channels, is_ok = read_wav(wav_path)
```

`read_wav` (in `wav.py`) opens the file, reads the raw sound data (PCM), and returns the sample rate and channel count.

**Format check**

```python
if not is_ok or sample_rate != 16000 or num_channels != 1:
    print("[ERROR] ... must be 16kHz mono")
```

The robot’s audio system expects a specific format. Convert your file with an audio editor if needed.

**Streaming in chunks**

```python
play_pcm_stream(audioClient, pcm_list, "example")
```

Large files aren’t sent in one giant packet. `play_pcm_stream` splits the audio into chunks and sends them one after another with short delays — like buffering a video stream.

Inside `wav.py`, each chunk is sent with:

```python
ret_code, _ = client.PlayStream(stream_name, stream_id, chunk)
```

**Stopping playback**

```python
audioClient.PlayStop("example")
```

Tells the robot to stop the stream named `"example"` when finished.

---

## 10 — Volume control (`10_volume.py`)

### What it does

Either **read** the current speaker volume or **set** it to a value between 0 and 100.

```bash
python3 10_volume.py enp0s31f6 --get
python3 10_volume.py enp0s31f6 --set 50
```

### Key ideas in the code

**Mutually exclusive options**

```python
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--get", ...)
group.add_argument("--set", type=int, ...)
```

You must pick `--get` **or** `--set`, not both. `argparse` enforces that for you.

**Getting volume**

```python
error_code, data = audio.GetVolume()
current_vol = data.get('volume', 'unknown')
```

RPC calls often return a pair: `(error_code, data)`. Code `0` means success; `data` is a dictionary with the actual value.

**Setting volume safely**

```python
vol_target = max(0, min(100, args.set))
audio.SetVolume(vol_target)
```

`max(0, min(100, args.set))` **clamps** your number into the valid range — so typing `150` becomes `100`, and `-5` becomes `0`.

---

## 11 — Text-to-speech (`11_tts.py`)

### What it does

The robot **speaks** text you type — in English or Chinese. It also waves its hand while talking, so it feels more interactive.

```bash
python3 11_tts.py enp0s31f6 --lang en --text "Hello, how are you today?"
python3 11_tts.py enp0s31f6 --lang ch --text "你好，今天怎么样？"
```

### Key ideas in the code

**Language → speaker id**

```python
speaker_id = 0 if args.lang == "ch" else 1
```

The robot uses `0` for Chinese and `1` for English. Your `--lang` choice picks the right voice.

**Combining motion and speech**

```python
sport_client.WaveHand()
audio_client.TtsMaker(args.text, speaker_id)
time.sleep(5)
```

Two clients work together: `LocoClient` waves the hand, then `AudioClient` converts text to speech. The 5-second sleep gives the robot time to finish talking before the program exits.

---

## Helper files

### `loco_helpers.py`

Shared functions for script 03 (and similar labs):

- `get_fsm_id(client)` — ask the robot for its current FSM number
- `fsm_hint(fsm_id)` — turn that number into a short English description
- `FSM_HINTS` — the lookup table of known FSM ids

### `wav.py`

Used by script 09:

- `read_wav(filename)` — load a WAV file and extract raw PCM bytes
- `play_pcm_stream(client, pcm_list, ...)` — send audio to the robot in chunks
- `write_wave(...)` — create a WAV file (handy if you record or generate sounds in Python)

---

## Tips for learners

1. **Always run script 01 or 02 first** when something isn’t working — if you can’t receive data, later scripts won’t help.
2. **Read the warnings** before scripts that move the robot or change torque.
3. **Use `list`** in the interactive menus (scripts 03 and 04) to see all choices.
4. **Experiment with `--sequence` and `--pause`** in script 05 to build your own arm routines.
5. When editing code, change one thing at a time and run again — that’s the fastest way to learn what each line does.

Happy coding with your Unitree R1!
