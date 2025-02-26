import json
import cv2
import base64
import threading
import time
from datetime import datetime
from websocket_server import WebsocketServer
import logging
import numpy as np
from shared.image import SharedImage
from interfaces.pose3d import ListenerPose3d
import re
import os
from map import MAP


# Graphical User Interface Class
class GUI:
    # Initialization function
    # The actual initialization
    def __init__(self, host, hal):
        t = threading.Thread(target=self.run_server)

        self.payload = {'image': '', 'map': '', 'array': ''}
        self.server = None
        self.client = None

        self.host = host

        self.shared_image = SharedImage("numpyimage")
        
        self.array_lock = threading.Lock()
        self.array = None

        self.acknowledge = False
        self.acknowledge_lock = threading.Lock()

        self.mapXY = None
        self.worldXY = None
        # Take the console object to set the same websocket and client
        self.hal = hal
        t.start()

        # Create the lap object
        self.pose3d_object = ListenerPose3d("/taxi_holo/odom")
        self.map = MAP(self.pose3d_object)

    # Function to get the client
    # Called when a new client is received
    def get_client(self, client, server):
        self.client = client

    # Function to get value of Acknowledge
    def get_acknowledge(self):
        self.acknowledge_lock.acquire()
        acknowledge = self.acknowledge
        self.acknowledge_lock.release()

        return acknowledge

    # Function to get value of Acknowledge
    def set_acknowledge(self, value):
        self.acknowledge_lock.acquire()
        self.acknowledge = value
        self.acknowledge_lock.release()

    # encode the image data to be sent to websocket
    def payloadImage(self):
        image = self.shared_image.get()
        payload = {'image': '', 'shape': ''}
    	
        shape = image.shape
        frame = cv2.imencode('.PNG', image)[1]
        encoded_image = base64.b64encode(frame)
        
        payload['image'] = encoded_image.decode('utf-8')
        payload['shape'] = shape
        
        return payload

    def showNumpy(self, image):
        processed_image = np.stack((image,) * 3, axis=-1)
        self.shared_image.add(processed_image)

    # Process the array(ideal path) to be sent to websocket
    def showPath(self, array):
        self.array_lock.acquire()

        strArray = ''.join(str(e) for e in array)

        # Remove unnecesary spaces in the array to avoid JSON syntax error in javascript
        strArray = re.sub(r"\[[ ]+", "[", strArray)
        strArray = re.sub(r"[ ]+", ", ", strArray)
        strArray = re.sub(r",[ ]+]", "]", strArray)
        strArray = re.sub(r",,", ",", strArray)
        strArray = re.sub(r"]\[", "],[", strArray)
        strArray = "[" + strArray + "]"

        self.array = strArray
        self.array_lock.release()

    def getTargetPose(self):
        if (self.worldXY != None):
            return [self.worldXY[1], self.worldXY[0]]
        else:
            return None

    # Update the gui
    def update_gui(self):
        # Payload Image Message
        payload = self.payloadImage()
        self.payload["image"] = json.dumps(payload)

        self.payload["array"] = self.array
        # Payload Map Message
        pos_message1 = self.map.getTaxiCoordinates()
        # print(self.pose3d_object.getPose3d())
        ang_message = self.map.getTaxiAngle()
        pos_message = str(pos_message1 + ang_message)
        # print("pos2 : {} ,  ang : {}".format(pos_message,ang_message))
        self.payload["map"] = pos_message

        message = "#gui" + json.dumps(self.payload)
        self.server.send_message(self.client, message)

        return list(pos_message1)

    # Function to read the message from websocket
    # Gets called when there is an incoming message from the client
    def get_message(self, client, server, message):
        # Acknowledge Message for GUI Thread
        if (message[:4] == "#ack"):
            self.set_acknowledge(True)

        # Check for mouse click data on the map
        elif (message[:5] == "#pick"):
            data = eval(message[5:])
            self.mapXY = data
            x, y = self.mapXY
            worldx, worldy = self.map.gridToWorld(x, y)
            self.worldXY = [worldx, worldy]
            print("World : {}".format(self.worldXY))

    # Activate the server
    def run_server(self):
        self.server = WebsocketServer(port=2303, host=self.host)
        self.server.set_fn_new_client(self.get_client)
        self.server.set_fn_message_received(self.get_message)

        home_dir = os.path.expanduser('~')

        logged = False
        while not logged:
            try:
                f = open(f"{home_dir}/ws_gui.log", "w")
                f.write("websocket_gui=ready")
                f.close()
                logged = True
            except:
                time.sleep(0.1)

        self.server.run_forever()

    # Function to reset
    def reset_gui(self):
        self.map.reset()

# This class decouples the user thread
# and the GUI update thread
class ThreadGUI:
    def __init__(self, gui):
        self.gui = gui
        # Time variables
        self.ideal_cycle = 80
        self.measured_cycle = 80
        self.iteration_counter = 0

    # Function to start the execution of threads
    def start(self):
        self.measure_thread = threading.Thread(target=self.measure_thread)
        self.thread = threading.Thread(target=self.run)

        self.measure_thread.start()
        self.thread.start()

        print("GUI Thread Started!")

    # The measuring thread to measure frequency
    def measure_thread(self):
        while (self.gui.client == None):
            pass

        previous_time = datetime.now()
        while (True):
            # Sleep for 2 seconds
            time.sleep(2)

            # Measure the current time and subtract from previous time to get real time interval
            current_time = datetime.now()
            dt = current_time - previous_time
            ms = (dt.days * 24 * 60 * 60 + dt.seconds) * 1000 + dt.microseconds / 1000.0
            previous_time = current_time

            # Get the time period
            try:
                # Division by zero
                self.measured_cycle = ms / self.iteration_counter
            except:
                self.measured_cycle = 0

            # Reset the counter
            self.iteration_counter = 0

    def run(self):
        while (self.gui.client == None):
            pass

        while (True):
            start_time = datetime.now()
            self.gui.update_gui()
            acknowledge_message = self.gui.get_acknowledge()

            while (acknowledge_message == False):
                acknowledge_message = self.gui.get_acknowledge()

            self.gui.set_acknowledge(False)

            finish_time = datetime.now()
            self.iteration_counter = self.iteration_counter + 1

            dt = finish_time - start_time
            ms = (dt.days * 24 * 60 * 60 + dt.seconds) * 1000 + dt.microseconds / 1000.0
            if (ms < self.ideal_cycle):
                time.sleep((self.ideal_cycle - ms) / 1000.0)
