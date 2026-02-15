# LUSI Science Module

This repository contains Python scripts for controlling the hardware components of the **Lehigh University Space Initiative (LUSI) Science Module**.  
The scripts are designed to run on a Raspberry Pi and provide interfaces for actuators (motors, servos) and sensors (load cell with HX711).  

---

## Hardware_Controllers

### Motor Controller
Run with:
python Hardware_Controllers/Motor_Controller_CLI.py

Controls 4 motors via an interactive terminal interface:

Motors:
- Motor 1: Auger (NEO 550 via Spark MAX) — digs soil, forward only
- Motor 2: Platform (NEO 550 via Spark MAX) — raises/lowers platform, bidirectional
- Motor 3: Chamber Lid (SM-S2309S servo) — rotates testing chamber lid
- Motor 4: Soil Dropper (SG92R micro servo) — rotates soil dropper lid

Keybinds:
- 1/2/3/4 → Select a motor
- ENTER → Activate the selected motor
- ↑ / ↓ → Speed ±5% (NEO 550) or angle ±1° (servos)
- r → Reverse direction (Platform motor only)
- x → Stop all motors immediately
- q → Quit program

### Mass Sensor Controller
Run with:
python Hardware_Controllers/mass_sensor_controller.py

- Tares automatically on startup
- Prints weight in grams every second
- Stop with CTRL+C

---

## Dependencies
Install required Python libraries before running the scripts:
- pip install RPi.GPIO
- pip install hx711

---

## Notes
- Scripts require a Raspberry Pi with GPIO access
- Output is printed to the terminal for monitoring and debugging