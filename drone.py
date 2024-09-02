# from trello import TrelloClient  trello drone from trello import TrelloClient
import cv2 # opencv pip install opencv-python
# import tello  trello pip install tello-python
# press and wait until it flashes orange and connect to the wifi
from djitellopy import Tello  #pip install djitellopy


tello = Tello()

tello.connect()
tello.takeoff()

tello.move_left(100)
tello.rotate_counter_clockwise(90)
tello.move_forward(100)

tello.land()

