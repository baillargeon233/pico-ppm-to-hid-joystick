# Temporary CircuitPython diagnostic for Raspberry Pi Pico 2.
# Copy this file to CIRCUITPY/code.py after installing the matching boot.py.

import struct
import time

import board
import pulseio
import usb_hid


# PPM input configuration
PPM_PIN = board.GP2
PPM_ACTIVE_HIGH = True
NUM_CHANNELS = 8
FRAME_LENGTH_US = 22500
PULSE_LENGTH_US = 300

# Receiver signal validation
PULSE_TOLERANCE_US = 100
SYNC_GAP_US = 3000
CHANNEL_MIN_US = 900
CHANNEL_MAX_US = 2100
FRAME_LENGTH_TOLERANCE_US = 5000

# HID and failsafe configuration
CHANNEL_REVERSE = (1, 1, 1, 1, 1, 1, 1, 1)
FAILSAFE_SECONDS = 0.25
STATUS_INTERVAL_SECONDS = 1.0
HID_REPORT_INTERVAL_SECONDS = 0.02

if not 1 <= NUM_CHANNELS <= 8:
    raise ValueError("NUM_CHANNELS must be between 1 and 8")

# Verify that boot.py exposed a Game Pad interface.
if not usb_hid.devices:
    raise RuntimeError("No USB HID devices enabled; check boot.py and reboot")

gamepad = usb_hid.devices[0]
if gamepad.usage_page != 0x01 or gamepad.usage != 0x05:
    raise RuntimeError(
        "First HID device is not a Generic Desktop Game Pad; "
        "check boot.py and reboot"
    )

print("USB HID Game Pad detected: PASS")
print("PPM input: GP2; active high:", PPM_ACTIVE_HIGH)
print("Expected channels:", NUM_CHANNELS)
print("Expected frame length (us):", FRAME_LENGTH_US)
print("Frame length tolerance (us):", FRAME_LENGTH_TOLERANCE_US)
print("Expected active pulse (us):", PULSE_LENGTH_US, "+/-", PULSE_TOLERANCE_US)
print("Waiting for valid PPM frames...")

pulses = pulseio.PulseIn(
    PPM_PIN,
    maxlen=64,
    idle_state=not PPM_ACTIVE_HIGH,
)

channels = [1500] * 8
channel_min_seen = [65535] * 8
channel_max_seen = [0] * 8
frame_channels = []
frame_elapsed_us = 0
pending_active_pulse_us = 0
expect_active_pulse = True
frame_invalid = False
last_valid_frame_time = 0.0
last_report = None
last_report_attempt = 0.0
last_status_time = time.monotonic()

sync_count = 0
valid_frame_count = 0
bad_frame_count = 0
pulse_width_error_count = 0
pulse_width_error_samples = 0
hid_send_count = 0
hid_error_count = 0

pulse_min_us = max(1, PULSE_LENGTH_US - PULSE_TOLERANCE_US)
pulse_max_us = PULSE_LENGTH_US + PULSE_TOLERANCE_US


def channel_to_axis(value_us, reverse):
    value_us = max(CHANNEL_MIN_US, min(CHANNEL_MAX_US, value_us))
    value = ((value_us - CHANNEL_MIN_US) * 65534) // (
        CHANNEL_MAX_US - CHANNEL_MIN_US
    ) - 32767
    return value * reverse


def print_status(now):
    if valid_frame_count:
        age = now - last_valid_frame_time
        ppm_state = "PASS" if age <= FAILSAFE_SECONDS else "FAILSAFE"
        stable_state = "PASS" if valid_frame_count >= 10 else "WARMING"
    else:
        age = now - startup_time
        ppm_state = "NO SIGNAL"
        stable_state = "WAITING"

    channel_values = ", ".join(
        "CH{}={}".format(index + 1, channels[index])
        for index in range(NUM_CHANNELS)
    )
    channel_ranges = ", ".join(
        "{}:{}-{}".format(
            index + 1,
            channel_min_seen[index],
            channel_max_seen[index],
        )
        for index in range(NUM_CHANNELS)
        if channel_max_seen[index] > 0
    )
    if not channel_ranges:
        channel_ranges = "not observed yet"

    print(
        "PPM={} ({}, frames={}, syncs={}, bad={}, pulse-width-errors={}, "
        "age={:.2f}s)".format(
            ppm_state,
            stable_state,
            valid_frame_count,
            sync_count,
            bad_frame_count,
            pulse_width_error_count,
            age,
        )
    )
    print("  " + channel_values)
    print("  observed channel ranges (us): " + channel_ranges)
    print(
        "USB HID sends={} errors={}".format(
            hid_send_count,
            hid_error_count,
        )
    )


startup_time = time.monotonic()

while True:
    while len(pulses):
        duration_us = pulses.popleft()

        # A sync gap is long regardless of which phase the decoder expected.
        if duration_us >= SYNC_GAP_US:
            frame_elapsed_us += duration_us
            sync_count += 1
            frame_length_ok = (
                abs(frame_elapsed_us - FRAME_LENGTH_US)
                <= FRAME_LENGTH_TOLERANCE_US
            )
            channel_count_ok = len(frame_channels) == NUM_CHANNELS

            if frame_length_ok and channel_count_ok and not frame_invalid:
                for index in range(NUM_CHANNELS):
                    value = frame_channels[index]
                    channels[index] = value
                    channel_min_seen[index] = min(
                        channel_min_seen[index], value
                    )
                    channel_max_seen[index] = max(
                        channel_max_seen[index], value
                    )
                valid_frame_count += 1
                last_valid_frame_time = time.monotonic()
            else:
                bad_frame_count += 1
                if bad_frame_count <= 3:
                    print(
                        "Rejected frame: length={}us (expected {} +/- {}), "
                        "channels={} (expected {}), malformed={}".format(
                            frame_elapsed_us,
                            FRAME_LENGTH_US,
                            FRAME_LENGTH_TOLERANCE_US,
                            len(frame_channels),
                            NUM_CHANNELS,
                            frame_invalid,
                        )
                    )

            frame_channels = []
            frame_elapsed_us = 0
            frame_invalid = False
            pending_active_pulse_us = 0
            expect_active_pulse = True
        elif expect_active_pulse:
            frame_elapsed_us += duration_us
            if pulse_min_us <= duration_us <= pulse_max_us:
                pending_active_pulse_us = duration_us
            else:
                pending_active_pulse_us = 0
                frame_invalid = True
                pulse_width_error_count += 1
                if pulse_width_error_samples < 8:
                    print("Out-of-range active pulse: {} us".format(duration_us))
                    pulse_width_error_samples += 1
            expect_active_pulse = False
        else:
            frame_elapsed_us += duration_us
            expect_active_pulse = True
            channel_us = pending_active_pulse_us + duration_us
            if pending_active_pulse_us and CHANNEL_MIN_US <= channel_us <= CHANNEL_MAX_US:
                frame_channels.append(channel_us)
            else:
                frame_invalid = True
            pending_active_pulse_us = 0

    now = time.monotonic()
    if now - last_valid_frame_time > FAILSAFE_SECONDS:
        channels = [1500] * 8

    report = struct.pack(
        "<8h",
        *[
            channel_to_axis(channels[index], CHANNEL_REVERSE[index])
            for index in range(8)
        ]
    )

    if (
        report != last_report
        and now - last_report_attempt >= HID_REPORT_INTERVAL_SECONDS
    ):
        last_report_attempt = now
        try:
            gamepad.send_report(report)
            last_report = report
            hid_send_count += 1
        except OSError as error:
            hid_error_count += 1
            if hid_error_count <= 3:
                print("USB HID send error:", error)

    if now - last_status_time >= STATUS_INTERVAL_SECONDS:
        print_status(now)
        last_status_time = now

    time.sleep(0.001)
