# CircuitPython boot.py for the Pico 2 PPM joystick diagnostic.
# Copy this file to CIRCUITPY/boot.py, then reset the board.

import usb_hid


GAMEPAD_DESCRIPTOR = bytes((
    0x05, 0x01,       # Usage Page (Generic Desktop)
    0x09, 0x05,       # Usage (Game Pad)
    0xA1, 0x01,       # Collection (Application)
    0x16, 0x01, 0x80, # Logical Minimum (-32767), signed 16-bit
    0x26, 0xFF, 0x7F, # Logical Maximum (32767)
    0x75, 0x10,       # Report Size (16 bits)
    0x95, 0x01,       # One value for each axis usage
    0x09, 0x30, 0x81, 0x02,  # X
    0x09, 0x31, 0x81, 0x02,  # Y
    0x09, 0x32, 0x81, 0x02,  # Z
    0x09, 0x33, 0x81, 0x02,  # Rx
    0x09, 0x34, 0x81, 0x02,  # Ry
    0x09, 0x35, 0x81, 0x02,  # Rz
    0x09, 0x36, 0x81, 0x02,  # Slider
    0x09, 0x37, 0x81, 0x02,  # Dial
    0xC0,             # End Collection
))

gamepad = usb_hid.Device(
    report_descriptor=GAMEPAD_DESCRIPTOR,
    usage_page=0x01,
    usage=0x05,
    report_ids=(0,),
    in_report_lengths=(16,),
    out_report_lengths=(0,),
)

usb_hid.enable((gamepad,))
