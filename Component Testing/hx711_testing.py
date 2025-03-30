import time
from hx711 import HX711

# Define GPIO pins
DT_PIN = 27  # Change to match your setup
SCK_PIN = 17  # Change to match your setup

# Initialize HX711
hx = HX711(DT_PIN, SCK_PIN)

# Tare the scale (set to zero)
print("Taring... Please remove all weight from the load cell.")
hx.tare()
print("Tare complete.")

while True:
    try:
        weight = hx.get_weight(5)  # Read weight with 5 samples for stability
        print(f"Weight: {weight:.2f} g")  # Adjust this based on calibration
        hx.power_down()
        hx.power_up()
        time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
        break
