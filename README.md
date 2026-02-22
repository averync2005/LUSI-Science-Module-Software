# LUSI Science Module

This repository contains Python scripts for controlling the hardware components of the **Lehigh University Space Initiative (LUSI) Science Module**.  
The scripts are designed to run on a Raspberry Pi and provide interfaces for actuators (motors, servos) and sensors (load cell, camera).  

---

## Motor Controller
Run with:
python Motor_Controller_CLI.py

Controls 4 motors via an interactive terminal interface:

Motors:
- Motor 1: Auger (NEO 550 via Spark MAX) - digs soil, forward only
- Motor 2: Platform (NEO 550 via Spark MAX) - raises/lowers platform, bidirectional
- Motor 3: Chamber Lid (SM-S2309S servo) - rotates testing chamber lid
- Motor 4: Soil Dropper (SG92R micro servo) - rotates soil dropper lid

GPIO Pin Assignments (BCM):
- Auger --> GPIO 12
- Platform --> GPIO 13
- Chamber Lid --> GPIO 18
- Soil Dropper --> GPIO 19

Keybinds:
- 1/2/3/4 --> Select a motor
- ENTER --> Activate the selected motor
- UP / DOWN --> Speed +/-5% (NEO 550) or angle +/-1° (servos)
- r --> Reverse direction (Platform motor only)
- x --> Stop all motors immediately
- q --> Quit program

---

## Weight Sensor
Run with:
python Weight_Sensor.py

- Reads weight from a load cell via the HX711 amplifier board
- Tares automatically on startup
- Prints weight in grams every second
- Stop with CTRL+C
- GPIO pins: DT --> GPIO 27, SCK --> GPIO 17

---

## Camera System
A single script that combines live camera preview, camera scanning, and serial port listing.

### Live Preview (default)
python Camera_System.py
python Camera_System.py --index 0 --width 640 --height 480

Live camera preview with optional GNSS overlay, scale bar, photo/video capture.
Run with --help for all options.

### Scan for Cameras
python Camera_System.py scan

Scans camera indices 0-4 and reports which are accessible.

### List Serial Ports
python Camera_System.py ports
python Camera_System.py ports --probe

Lists available serial ports. Use --probe to check each port for GNSS/NMEA signals.

---

## Dependencies
Install required Python libraries:
pip install -r requirements.txt

Or individually:
- pip install RPi.GPIO
- pip install git+https://github.com/tatobari/hx711py.git
- pip install opencv-python
- pip install pyserial

---

## Notes
- Scripts require a Raspberry Pi with GPIO access
- Output is printed to the terminal for monitoring and debugging