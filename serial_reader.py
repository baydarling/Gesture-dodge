import serial
import time

arduino = serial.Serial("COM11", 115200, timeout=1)

time.sleep(2)

while True:
    data = arduino.readline()
    message = data.decode("ascii").strip()

    if message in ("L:0", "L:1", "L:2"):
        lane = int(message[2])
        print(lane)