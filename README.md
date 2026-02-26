# LUSI Science Module

This repository contains Python scripts for controlling the hardware components of the **Lehigh University Space Initiative (LUSI) Science Module**.  
The scripts are designed to run on a Raspberry Pi and provide interfaces for actuators (motors, servos) and sensors (load cell, camera).  

---

## Motor Controller
Run with:
sudo pigpiod              # start the pigpio daemon (once per boot)
python Motor_Controller_CLI.py

Controls 4 motors via a command-line interface. The command menu and motor list reprint before every prompt.

Commands:
- 1 / 2 / 3 / 4 --> Select a motor and set its speed or angle
- off --> Turn off a single motor (prompts for motor number)
- stop / x --> Stop all motors immediately
- status / s --> Show motor status
- help / h --> Reprint the command menu
- q --> Quit program

Setting a NEO 550 motor to 0% speed turns it off. Setting a servo to 0° resets the angle.

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

## Spectrometer
Run with:
python Spectrometer.py
python Spectrometer.py --device 0 --fps 30
python Spectrometer.py --waterfall
python Spectrometer.py --fullscreen

Captures spectral data from a USB camera-based diffraction grating spectrometer and displays a
real-time wavelength vs. intensity graph with peak detection, calibration, and data export.

USB port: Plug the spectrometer camera into one of the **blue USB 3.0 ports** on the Pi 4 for best
bandwidth. The black USB 2.0 ports will also work but may limit frame rate.

Find your camera device number with: v4l2-ctl --list-devices

Key bindings:
- h --> Toggle peak hold
- m --> Toggle measurement cursor (shows wavelength at mouse position)
- p --> Toggle pixel recording mode (click peaks to select calibration points)
- c --> Run calibration (enter known wavelengths in the terminal)
- x --> Clear calibration points
- s --> Save spectrum as PNG + CSV
- o / l --> Savitzky-Golay filter up / down
- i / k --> Peak distance up / down
- u / j --> Label threshold up / down
- q --> Quit

Options:
- --device N --> USB camera device number (default: 0)
- --fps N --> Frame rate (default: 30)
- --fullscreen --> Fullscreen mode (800x480)
- --waterfall --> Enable waterfall display (spectral changes over time)

Calibration data is saved to caldata.txt and persists across restarts.

---

## Dependencies
Install required Python libraries:
pip install -r requirements.txt

Or individually:
- pip install RPi.GPIO
- pip install pigpio
- pip install git+https://github.com/tatobari/hx711py.git
- pip install opencv-python
- pip install numpy
- pip install pyserial

---

## Notes
- Scripts require a Raspberry Pi with GPIO access
- Output is printed to the terminal for monitoring and debugging