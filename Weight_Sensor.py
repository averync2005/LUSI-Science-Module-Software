#!/usr/bin/env python3
# This shebang line tells Linux and macOS to use Python 3 when the script is
# run directly from the terminal (e.g., ./Weight_Sensor.py). On Windows,
# this line is ignored - you run scripts with "python Weight_Sensor.py" instead.


#####################################################################################################################
# LUSI Science Module - Weight Sensor
#
# This script reads weight data from a load cell connected to the Raspberry Pi through an HX711 amplifier board.
# The HX711 is a 24-bit analog-to-digital converter (ADC) designed specifically for weight scale applications.
# It communicates with the Pi over two GPIO pins (data and clock).
#
# How it works:
#   1. On startup, the script "tares" (zeroes) the load cell so the current reading becomes 0 grams
#   2. It then enters a continuous loop, printing the measured weight once per second
#   3. Between reads, the HX711 is powered down and back up to reduce sensor drift
#   4. Press CTRL+C to stop the script
#####################################################################################################################




#####################################################################################################################
# Importing Program Libraries
#   - time:
#       - Adds delays to the program (1-second pause between weight readings)
#       - Prevents the script from reading the sensor too rapidly, which would
#         increase noise and power consumption
#   - RPi.GPIO:
#       - Controls the Raspberry Pi's GPIO (General Purpose Input/Output) pins
#       - Provides GPIO cleanup on exit to release pins back to the system so
#         other programs can use them without conflicts
#   - hx711:
#       - Provides the HX711 class for communicating with the load cell amplifier
#       - Handles the low-level 24-bit data protocol over the data and clock pins
#       - Enables reading weight data from the sensor through GPIO pins
#####################################################################################################################

import time
import RPi.GPIO as GPIO
from hx711 import HX711




#####################################################################################################################
# GPIO Pin Assignments (BCM numbering)
#   - DT_PIN (Data pin) receives weight data output from the HX711 board
#   - SCK_PIN (Clock pin) sends timing pulses to the HX711 board
#   - BCM = Broadcom pin numbering (the numbers printed on Pi pinout diagrams)
#   - Change these if you wire the HX711 to different GPIO pins
#####################################################################################################################

DT_PIN = 27  # HX711 data output --> GPIO 27
SCK_PIN = 17  # HX711 clock input --> GPIO 17




#####################################################################################################################
# Initializing the Load Cell
#   - Creates an HX711 instance using the defined GPIO pins
#   - The HX711 reads analog voltage from the load cell and converts it to a digital value
#   - The load cell works by measuring tiny deformations caused by weight - the HX711
#     amplifies this signal so the Raspberry Pi can read it accurately
#####################################################################################################################

hx = HX711(DT_PIN, SCK_PIN)




#####################################################################################################################
# Taring the Load Cell
#   - "Taring" means setting the current reading as zero (like pressing the zero button
#     on a kitchen scale)
#   - This removes any offset caused by the weight of the container or mounting hardware
#   - Make sure nothing is on the load cell when this runs, otherwise the weight of
#     whatever is on it will be subtracted from all future readings
#####################################################################################################################

print("[INFO] Taring... Please remove all weight from the load cell.")
hx.tare()
print("[INFO] Tare complete.")




#####################################################################################################################
# Reading Weight in a Continuous Loop
#   - Collects averaged weight data from the HX711 (average of 5 samples per reading
#     to reduce noise and give more stable measurements)
#   - Prints weight in grams (formatted to two decimal places)
#   - Powers the HX711 down and back up between reads to reduce sensor drift (the tiny
#     gradual change in readings that happens when the chip gets warm)
#   - Runs until manually stopped with a keyboard interrupt (CTRL+C)
#   - GPIO pins are always cleaned up on exit (even if the program crashes) so other
#     programs can use the pins without conflicts
#####################################################################################################################

try:
    while True:
        weight = hx.get_weight(5)  # Average of 5 samples for stability
        weightLine = f"Weight: {weight:.2f} g"
        print(weightLine)
        hx.power_down()
        hx.power_up()
        time.sleep(1)
except KeyboardInterrupt:
    print("[INFO] Exiting... Program stopped.")
finally:
    GPIO.cleanup()
    print("[INFO] GPIO cleaned up safely.")
