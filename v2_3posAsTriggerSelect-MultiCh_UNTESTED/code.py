# CircuitPython PPM ---> HID joystick for Raspberry Pi Pico 2.

import struct
import time

import board
import pulseio
import usb_hid


# PPM input configuration
PPM_PIN = board.GP2
PPM_ACTIVE_HIGH = True
# Set to the receiver's PPM channel count, from 8 through 12.
NUM_CHANNELS = 10
MODE_SELECT_ENABLED = True
FRAME_LENGTH_US = 22500
PULSE_LENGTH_US = 300

# Receiver signal validation
PULSE_TOLERANCE_US = 100
SYNC_GAP_US = 3000
CHANNEL_MIN_US = 900
CHANNEL_MAX_US = 2100
FRAME_LENGTH_TOLERANCE_US = 5000
BUTTON_THRESHOLD_US = 1500
THREE_POSITION_LOW_MAX_US = 1300
THREE_POSITION_HIGH_MIN_US = 1700

# HID and failsafe configuration
CHANNEL_REVERSE = (1, 1, 1, 1, 1, 1, 1, 1)
FAILSAFE_SECONDS = 0.25
HID_REPORT_INTERVAL_SECONDS = 0.02

if not 8 <= NUM_CHANNELS <= 12:
    raise ValueError("NUM_CHANNELS must be between 8 and 12")

# Verify that boot.py exposed a Game Pad interface.
if not usb_hid.devices:
    raise RuntimeError("No USB HID devices enabled; check boot.py and reboot")

gamepad = usb_hid.devices[0]
if gamepad.usage_page != 0x01 or gamepad.usage != 0x05:
    raise RuntimeError(
        "First HID device is not a Generic Desktop Game Pad; "
        "check boot.py and reboot"
    )

pulses = pulseio.PulseIn(
    PPM_PIN,
    maxlen=64,
    idle_state=not PPM_ACTIVE_HIGH,
)

channels = [1500] * NUM_CHANNELS
frame_channels = []
frame_elapsed_us = 0
pending_active_pulse_us = 0
expect_active_pulse = True
frame_invalid = False
last_valid_frame_time = 0.0
last_report = None
last_report_attempt = 0.0

pulse_min_us = max(1, PULSE_LENGTH_US - PULSE_TOLERANCE_US)
pulse_max_us = PULSE_LENGTH_US + PULSE_TOLERANCE_US


def channel_to_axis(value_us, reverse):
    value_us = max(CHANNEL_MIN_US, min(CHANNEL_MAX_US, value_us))
    value = ((value_us - CHANNEL_MIN_US) * 65534) // (
        CHANNEL_MAX_US - CHANNEL_MIN_US
    ) - 32767
    return value * reverse


while True:
    while len(pulses):
        duration_us = pulses.popleft()

        # A sync gap is long regardless of which phase the decoder expected.
        if duration_us >= SYNC_GAP_US:
            frame_elapsed_us += duration_us
            frame_length_ok = (
                abs(frame_elapsed_us - FRAME_LENGTH_US)
                <= FRAME_LENGTH_TOLERANCE_US
            )
            channel_count_ok = len(frame_channels) == NUM_CHANNELS

            if frame_length_ok and channel_count_ok and not frame_invalid:
                for index in range(NUM_CHANNELS):
                    channels[index] = frame_channels[index]
                last_valid_frame_time = time.monotonic()

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
        channels = [1500] * NUM_CHANNELS

    button_bits = 0
    if MODE_SELECT_ENABLED:
        if channels[4] >= BUTTON_THRESHOLD_US:
            if channels[7] >= THREE_POSITION_HIGH_MIN_US:
                button_bits |= 1 << 0
            elif channels[7] <= THREE_POSITION_LOW_MAX_US:
                button_bits |= 1 << 2
            else:
                button_bits |= 1 << 1

        for channel_index in (5, 6):
            if channels[channel_index] >= BUTTON_THRESHOLD_US:
                button_bits |= 1 << (channel_index - 2)

        for channel_index in range(8, NUM_CHANNELS):
            if channels[channel_index] >= BUTTON_THRESHOLD_US:
                button_bits |= 1 << (channel_index - 3)
    else:
        for channel_index in range(4, NUM_CHANNELS):
            if channel_index == 7:
                if channels[channel_index] <= THREE_POSITION_LOW_MAX_US:
                    button_bits |= 1 << 3
                elif channels[channel_index] >= THREE_POSITION_HIGH_MIN_US:
                    button_bits |= 1 << 4
            elif channels[channel_index] >= BUTTON_THRESHOLD_US:
                button_index = (
                    channel_index - 4 if channel_index < 7 else channel_index - 3
                )
                button_bits |= 1 << button_index

    report_values = [
        channel_to_axis(channels[index], CHANNEL_REVERSE[index])
        for index in range(4)
    ]
    report_values.append(button_bits)
    report = struct.pack("<4hH", *report_values)

    if (
        report != last_report
        and now - last_report_attempt >= HID_REPORT_INTERVAL_SECONDS
    ):
        last_report_attempt = now
        try:
            gamepad.send_report(report)
            last_report = report
        except OSError:
            pass

    time.sleep(0.001)
