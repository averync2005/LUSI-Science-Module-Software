# LUSI Science Module

This repository contains Python scripts for controlling the hardware components of the **Lehigh University Space Initiative (LUSI) Science Module**.  
The scripts are designed to run on a Raspberry Pi and provide interfaces for actuators (motors, servos) and sensors (load cell with HX711).  

---

## Hardware_Controllers

### Motor Controller
Run with:
python Hardware_Controllers/motor_controller.py

Controls:
- 1/2 → Motor1 forward/backward
- 3/4 → Motor2 forward/backward
- a/d/f → Servo to 0°, 90°, 180°
- s → Stop all motors
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