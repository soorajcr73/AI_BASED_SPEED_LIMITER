import warnings
warnings.filterwarnings("ignore")
import asyncio
import websockets
import json
import serial
import time

import pathlib
temp = pathlib.PosixPath
pathlib.PosixPath = pathlib.WindowsPath

import torch
import cv2
from collections import deque, Counter
from ocr import read_speed_sign

websocket_connection = None

async def connect_socket():
    global websocket_connection

    uri = "ws://127.0.0.1:8000/ws"

    websocket_connection = await websockets.connect(uri)


async def send_realtime_event(event):

    global websocket_connection

    try:

        if websocket_connection is None:
            await connect_socket()

        await websocket_connection.send(json.dumps(event))

    except:

        websocket_connection = None


def push_realtime_event(event):
    try:
        asyncio.run(send_realtime_event(event))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(send_realtime_event(event))
        finally:
            loop.close()

VALID_SPEEDS = [20,30,40,50,60,70,80,100]
DETECTION_SIZE = 736
SPEED_CONFIDENCE_THRESHOLD = 0.72
SIGN_CONFIDENCE_THRESHOLD = 0.62
SKIP_INTERVAL = 3
SIGN_WINDOW = 4
SIGN_CONFIRMATION_COUNT = 2
SIGN_COOLDOWN_FRAMES = 18
DEFAULT_DRIVE_STATE = "Standby"
ARDUINO_PORT = "COM3"
ARDUINO_BAUDRATE = 9600

LABEL_MAP = {
"compulsory_keep_left":"Compulsory Keep Left",
"curve_warning":"Curve Warning",
"dual_carriageway":"Dual Carriageway",
"gap_in_median":"Gap In Median",
"give_way":"Give Way",
"go_slow":"Go Slow",
"junction_warning":"Junction Ahead",
"merging_traffic":"Merging Traffic",
"no_parking":"No Parking",
"overtaking_prohibited":"No Overtaking",
"pass_either_way":"Pass Either Way",
"pedestrian_crossing":"Pedestrian Crossing",
"restriction_ends":"Restriction Ends",
"road_width_change":"Road Width Change",
"rumble_strip":"Rumble Strip",
"school_ahead":"School Ahead",
"signal_ahead":"Signal Ahead",
"speed_breaker":"Speed Breaker",
"speed_limit":"Speed Limit",
"stop":"Stop",
"turn_prohibited":"Turn Prohibited"
}

VALID_SIGNS = list(LABEL_MAP.keys())

SIGN_BEHAVIOR_RULES = {
    "School Ahead": {
        "target_speed": 25,
        "duration_frames": 90,
        "state": "School Zone",
        "message": "School zone detected. Applying a cautious speed cap."
    },
    "Pedestrian Crossing": {
        "target_speed": 20,
        "duration_frames": 75,
        "state": "Pedestrian Zone",
        "message": "Pedestrian crossing ahead. Slowing down for safety."
    },
    "Speed Breaker": {
        "target_speed": 15,
        "duration_frames": 60,
        "state": "Speed Breaker",
        "message": "Speed breaker detected. Reducing motor speed."
    },
    "Stop": {
        "target_speed": 0,
        "duration_frames": 45,
        "state": "Stop Required",
        "message": "Stop sign detected. Commanding a full stop."
    },
    "Go Slow": {
        "target_speed": 30,
        "duration_frames": 75,
        "state": "Caution",
        "message": "Go slow sign detected. Applying a temporary speed cap."
    },
    "Give Way": {
        "target_speed": 20,
        "duration_frames": 45,
        "state": "Yield",
        "message": "Give way sign detected. Reducing speed for merging traffic."
    }
}


model = torch.hub.load(
    '../yolov5',
    'custom',
    path='../yolov5/runs/train/exp/weights/best-new.pt',
    source='local'
)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

print("YOLOv5 model loaded successfully")

arduino = None


def connect_arduino():
    global arduino

    if arduino is not None and arduino.is_open:
        return arduino

    try:
        arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUDRATE, timeout=1)
        time.sleep(2)
        print(f"Arduino connected successfully on {ARDUINO_PORT}")
    except Exception as exc:
        arduino = None
        print(f"Arduino connection failed on {ARDUINO_PORT}: {exc}")

    return arduino


def send_speed_to_arduino(speed):
    board = connect_arduino()

    if board is None:
        print("Arduino not available, skipping speed send")
        return False

    try:
        board.write((str(speed) + "\n").encode())
        board.flush()
        print("Sent to Arduino:", speed)
        return True
    except Exception as exc:
        print("Arduino write failed:", exc)
        try:
            board.close()
        except Exception:
            pass
        globals()["arduino"] = None
        return False


def emit_progress_event(progress, processed_frames, total_frames, eta_seconds, stage):
    event = {
        "type": "progress",
        "stage": stage,
        "progress": progress,
        "processed_frames": processed_frames,
        "total_frames": total_frames,
        "eta_seconds": eta_seconds
    }
    print("SENDING PROGRESS EVENT:", event)
    push_realtime_event(event)


def normalize_speed(speed):
    if speed is None:
        return None
    return int(round(speed))


def determine_effective_speed(base_speed, active_behavior):
    if active_behavior is None:
        return normalize_speed(base_speed)

    override_speed = active_behavior["target_speed"]
    if base_speed is None:
        return normalize_speed(override_speed)

    return normalize_speed(min(base_speed, override_speed))


def emit_drive_command(time_stamp, events, effective_speed, base_speed, active_behavior, reason):
    drive_state = active_behavior["state"] if active_behavior else ("Speed Locked" if effective_speed is not None else DEFAULT_DRIVE_STATE)
    active_sign = active_behavior["sign"] if active_behavior else None
    detail = active_behavior["message"] if active_behavior else "Using the latest confirmed speed limit."

    event = {
        "type": "control",
        "time": time_stamp,
        "speed": effective_speed,
        "base_speed": base_speed,
        "active_sign": active_sign,
        "drive_state": drive_state,
        "reason": reason,
        "detail": detail
    }
    events.append(event)
    print("SENDING CONTROL EVENT:", event)
    push_realtime_event(event)
    send_speed_to_arduino(effective_speed if effective_speed is not None else 0)


def update_active_behavior(active_behavior, confirmed_sign, frame_count, time_stamp, events):
    if confirmed_sign == "Restriction Ends":
        cleared = active_behavior is not None
        if cleared:
            event = {
                "type": "behavior",
                "time": time_stamp,
                "sign": confirmed_sign,
                "state": DEFAULT_DRIVE_STATE,
                "message": "Restriction ends detected. Clearing temporary sign-based override.",
                "target_speed": None
            }
            events.append(event)
            print("SENDING BEHAVIOR EVENT:", event)
            push_realtime_event(event)
        return None, cleared

    rule = SIGN_BEHAVIOR_RULES.get(confirmed_sign)
    if rule is None:
        return active_behavior, False

    updated_behavior = {
        "sign": confirmed_sign,
        "target_speed": rule["target_speed"],
        "state": rule["state"],
        "message": rule["message"],
        "expires_at_frame": frame_count + rule["duration_frames"]
    }
    event = {
        "type": "behavior",
        "time": time_stamp,
        "sign": confirmed_sign,
        "state": rule["state"],
        "message": rule["message"],
        "target_speed": rule["target_speed"]
    }
    events.append(event)
    print("SENDING BEHAVIOR EVENT:", event)
    push_realtime_event(event)
    return updated_behavior, True


def process_video(input_path, output_path):
    speed_buffer = deque(maxlen=5)
    sign_history = deque(maxlen=SIGN_WINDOW)

    cap = cv2.VideoCapture(input_path)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if fps == 0:
        fps = 30

    if total_frames <= 0:
        total_frames = 1

    out = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*'avc1'),
        fps,
        (width, height)
    )

    events = []
    final_speed = None

    last_confirmed_speed = None
    last_commanded_speed = None
    last_sign_frame = {}
    active_behavior = None

    frame_count = 0
    start_time = time.time()
    last_reported_progress = -1

    emit_progress_event(
        progress=0,
        processed_frames=0,
        total_frames=total_frames,
        eta_seconds=None,
        stage="processing"
    )

    while True:

        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        progress = min(int((frame_count / total_frames) * 100), 100)
        elapsed = max(time.time() - start_time, 0.001)
        frames_per_second = frame_count / elapsed
        remaining_frames = max(total_frames - frame_count, 0)
        eta_seconds = round(remaining_frames / frames_per_second, 1) if frames_per_second > 0 else None

        if progress != last_reported_progress and (progress % 2 == 0 or progress == 100):
            emit_progress_event(
                progress=progress,
                processed_frames=frame_count,
                total_frames=total_frames,
                eta_seconds=eta_seconds,
                stage="processing"
            )
            last_reported_progress = progress

        if active_behavior and frame_count >= active_behavior["expires_at_frame"]:
            time_stamp = round(cap.get(cv2.CAP_PROP_POS_MSEC)/1000,2)
            expired_sign = active_behavior["sign"]
            expired_state = active_behavior["state"]
            active_behavior = None
            event = {
                "type": "behavior",
                "time": time_stamp,
                "sign": expired_sign,
                "state": DEFAULT_DRIVE_STATE,
                "message": f"{expired_state} override expired. Returning to the posted speed limit.",
                "target_speed": None
            }
            events.append(event)
            print("SENDING BEHAVIOR EVENT:", event)
            push_realtime_event(event)
            effective_speed = determine_effective_speed(last_confirmed_speed, active_behavior)
            if effective_speed != last_commanded_speed:
                emit_drive_command(
                    time_stamp=time_stamp,
                    events=events,
                    effective_speed=effective_speed,
                    base_speed=last_confirmed_speed,
                    active_behavior=active_behavior,
                    reason="Temporary sign rule expired"
                )
                last_commanded_speed = effective_speed
                final_speed = effective_speed

        if frame_count % SKIP_INTERVAL != 0:
            out.write(frame)
            continue

        # Use a slightly larger size and denser sampling to reduce missed signs.
        results = model(frame, size=DETECTION_SIZE)
        torch.cuda.empty_cache()

        frame_signs = set()

        for *box, conf, cls in results.xyxy[0]:

            confidence = float(conf)

            class_name = model.names[int(cls)]

            if class_name not in VALID_SIGNS:
                continue

            min_confidence = (
                SPEED_CONFIDENCE_THRESHOLD
                if class_name == "speed_limit"
                else SIGN_CONFIDENCE_THRESHOLD
            )

            if confidence < min_confidence:
                continue

            label = LABEL_MAP[class_name]

            print(f"Frame {frame_count} | Detected: {label} | confidence: {confidence:.2f}")

            x1, y1, x2, y2 = map(int, box)

            pad = 10
            x1 = max(0, x1-pad)
            y1 = max(0, y1-pad)
            x2 = min(frame.shape[1], x2+pad)
            y2 = min(frame.shape[0], y2+pad)

            crop = frame[y1:y2, x1:x2]

            if crop.size == 0:
                continue

            time_stamp = round(cap.get(cv2.CAP_PROP_POS_MSEC)/1000,2)

            if class_name == "speed_limit":
                speed, conf_score = read_speed_sign(crop)
                print("OCR SPEED:", speed)

                if speed in VALID_SPEEDS:
                    speed_buffer.append(speed)
                    if len(speed_buffer) >= 3:
                        stable_speed = Counter(speed_buffer).most_common(1)[0][0]
                        if stable_speed != last_confirmed_speed:
                            event = {
                                "time": time_stamp,
                                "speed": stable_speed,
                                "sign": None,
                                "type": "speed"
                            }

                            events.append(event)
                            print("SENDING REALTIME EVENT:", event)
                            push_realtime_event(event)
                            last_confirmed_speed = stable_speed
                            effective_speed = determine_effective_speed(last_confirmed_speed, active_behavior)
                            if effective_speed != last_commanded_speed:
                                emit_drive_command(
                                    time_stamp=time_stamp,
                                    events=events,
                                    effective_speed=effective_speed,
                                    base_speed=last_confirmed_speed,
                                    active_behavior=active_behavior,
                                    reason="Speed limit updated"
                                )
                                last_commanded_speed = effective_speed
                            final_speed = effective_speed
                        label = f"Speed {stable_speed}"
            else:
                frame_signs.add(label)

            cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,0),2)
            cv2.putText(frame, label, (x1,y1-10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

        sign_history.append(frame_signs)

        if len(sign_history) >= SIGN_CONFIRMATION_COUNT:
            recent_signs = set().union(*sign_history)

            for stable_sign in sorted(recent_signs):
                match_count = sum(1 for signs in sign_history if stable_sign in signs)
                last_frame = last_sign_frame.get(stable_sign, -SIGN_COOLDOWN_FRAMES)

                if match_count >= SIGN_CONFIRMATION_COUNT and (frame_count - last_frame) >= SIGN_COOLDOWN_FRAMES:
                    time_stamp = round(cap.get(cv2.CAP_PROP_POS_MSEC)/1000,2)
                    print("CONFIRMED SIGN:", stable_sign, "| hits:", match_count)
                    event = {
                        "time": time_stamp,
                        "speed": None,
                        "sign": stable_sign,
                        "type": "sign"
                    }

                    events.append(event)
                    print("SENDING REALTIME EVENT:", event)
                    push_realtime_event(event)
                    active_behavior, behavior_changed = update_active_behavior(
                        active_behavior=active_behavior,
                        confirmed_sign=stable_sign,
                        frame_count=frame_count,
                        time_stamp=time_stamp,
                        events=events
                    )
                    effective_speed = determine_effective_speed(last_confirmed_speed, active_behavior)
                    if behavior_changed or stable_sign in SIGN_BEHAVIOR_RULES:
                        if effective_speed != last_commanded_speed:
                            emit_drive_command(
                                time_stamp=time_stamp,
                                events=events,
                                effective_speed=effective_speed,
                                base_speed=last_confirmed_speed,
                                active_behavior=active_behavior,
                                reason=f"{stable_sign} rule applied"
                            )
                            last_commanded_speed = effective_speed
                            final_speed = effective_speed
                    last_sign_frame[stable_sign] = frame_count

        out.write(frame)
        del results
        torch.cuda.empty_cache()

    cap.release()
    out.release()

    emit_progress_event(
        progress=100,
        processed_frames=total_frames,
        total_frames=total_frames,
        eta_seconds=0,
        stage="completed"
    )

    return final_speed, events
