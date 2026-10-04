# pico-ppm-to-hid-joystick
**CircuitPython code for Raspberry Pi Pico 2 that converts RC controller PPM signals to USB HID joystick input**

I have many hours logged in various flight sims with my trusty FlySky TH-9X transmitter. I would use vJoy or similar software to convert the PPM signal into a virtual controller. While this works for most cases and is easy to set up, some game companies consider using virtual controllers as a bannable offense. While I understand the logic, this has prevented me from using my transmitter to fly in some games. You could spend the money for a newer transmitter... OR:

The code.py and boot.py files can be uploaded to a Raspberry Pi Pico (2, in my case) and will read the PPM signal from a transmitter on GPIO 2 by default. PLEASE USE A RESISTOR DIVIDER. 20k and 10k works fine, most transmitters operate the PPM at 5V. Especially the older ones like mine. 

This PPM signal is then converted into a HID packet that is sent off to a PC. The boot.py file ensures that the pi is detected specifically as a USB Joystick, and you should see it listed as such in device manager or in the HOTAS setup page of your game. In games it is usually detected as "CIRCUITPI HID".

The "Basic 8-channel" file will generate a HID joystick with the first 4 channels for the thumb stick axes, and the remaining as switches/buttons. The "Full-channel" file is more complex and is really only for my specific setup and needs, but feel free to poke around and modify it for your own use.

There are several important parameters at the top of the code that you will need to change to match your transmitter;
PPM_ACTIVE_HIGH       #PPM rising edge or pulse falling edge? True for rising, False for falling
FRAME_LENGTH_US     #I have OpenTX on my transmitter, and it lists the PPM packet size in milliseconds
PULSE_LENGTH_US       #300uS is the default for me

The rest of the code is just managing the USB interaction. 

Please note that there is a different boot.py file for each code.py file. Mixing them will create problems.
