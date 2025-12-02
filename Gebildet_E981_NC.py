import RPi.GPIO as GPIO
import time

PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

while True:
    if GPIO.input(PIN) == GPIO.HIGH:
        print("Porte OUVERTE")
    else:
        print("Porte FERMÉE")
    time.sleep(0.1)
