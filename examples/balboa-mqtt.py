#!/usr/bin/env python3

import logging
from operator import attrgetter
import paho.mqtt.client as mqtt
import pybalboa
import pybalboa.messages

import homie

logging.basicConfig(level=logging.INFO)

def on_mqtt_connect(client, userdata, flags, rc):
    global mqtt_connected
    logging.info("Connected to MQTT broker.")
    client.on_message = on_mqtt_message
    mqtt_connected = True

def on_mqtt_message(client, userdata, message):
    global spa_client
    if message.topic == "homie/hot-tub/spa-controller/pump-1/set":
        logging.info("Recevied Toggle Pump 1 command")
        msg = pybalboa.messages.TogglePump1Request();
    elif message.topic == "homie/hot-tub/spa-controller/pump-2/set":
        logging.info("Recevied Toggle Pump 2 command")
        msg = pybalboa.messages.TogglePump2Request();
    elif message.topic == "homie/hot-tub/spa-controller/pump-3/set":
        logging.info("Recevied Toggle Pump 3 command")
        msg = pybalboa.messages.TogglePump3Request();
    elif message.topic == "homie/hot-tub/spa-controller/light-1/set":
        logging.info("Recevied Toggle Light 1 command")
        msg = pybalboa.messages.ToggleLight1Request();
    elif message.topic == "homie/hot-tub/spa-controller/set-temperature/set":
        set_temperature = int(message.payload)
        logging.info("Recevied Set Temperature command: {}".format(set_temperature))
        msg = pybalboa.messages.SetTemperatureRequest(set_temperature);
    elif message.topic == "homie/hot-tub/spa-controller/raw-command/set":
        try:
            msg = pybalboa.messages.Message.from_bytes(message.payload)
        except ValueError:
            logging.error("Invalid raw command received")
            return
        logging.info("Raw command received: " + ",".join(map("{:02X}".format, bytes(msg))))
    else:
        return
    spa_client.send(msg)

def on_spa_message(msg):
    global mqtt_client, msg_cache, spa_properties
    try:
        msg = pybalboa.messages.StatusMessage.from_bytes(bytes(msg))
    except ValueError as e:
        return
    msg = bytes(msg.payload)
    logging.debug("Status Message received: " + ",".join(map("{:02X}".format, msg)))
    if mqtt_connected and msg != msg_cache:
        logging.info("Status changed, publishing data.")
        mqtt_client.publish("homie/hot-tub/spa-controller/status", msg)
        for property in spa_properties:
            if property.id == "priming":
                if property.value != msg[1] & 0x1:
                    property.value = msg[1] & 0x1
            elif property.id == "heating-mode":
                if property.value != msg[5] & 0x3:
                    property.value = msg[5] & 0x3
        msg_cache = msg


msg_cache = None
spa_client = None
mqtt_connected = False
mqtt_client = mqtt.Client("balboa")
mqtt_client.on_connect = on_mqtt_connect
logging.debug("Connecting to MQTT broker...")
mqtt_client.connect("bass")
mqtt_client.loop_start()
logging.debug("Starting Spa client...")
spa_client = pybalboa.BalboaSpaLocalController("/dev/ttyUSB0")
spa_client.onmessage = on_spa_message
mqtt_client.subscribe("homie/hot-tub/spa-controller/+/set")

spa_properties = []
spa_properties.append(homie.Property("priming", "Priming", "boolean"))
spa_properties.append(homie.Property("heating-mode", "Heating Mode", "enum", format="ready,rest,ready_in_rest", settable=True))
spa_properties.append(homie.Property("temperature-scale", "Temperature Scale", "enum", format="Fahrenheit,Celsius", settable=True))
spa_properties.append(homie.Property("24hr-time", "24-Hour Time", "boolean", settable=True))
spa_properties.append(homie.Property("heating", "heating", "boolean"))
spa_properties.append(homie.Property("temperature-range", "Temperature Range", "enum", format="high,low", settable=True))
spa_properties.append(homie.Property("circ-pump", "Circulation Pump", "boolean"))
spa_properties.append(homie.Property("pump-1", "Pump 1 Speed", "integer", format="0:2", settable=True))
spa_properties.append(homie.Property("pump-2", "Pump 2 Speed", "integer", format="0:2", settable=True))
spa_properties.append(homie.Property("pump-3", "Pump 3 Speed", "integer", format="0:2", settable=True))
spa_properties.append(homie.Property("light-1", "Light 1", "boolean", settable=True))
spa_controller = homie.Node("spa-controller", "Balboa Spa Controller", "spa", spa_properties)
hot_tub = homie.Device("hot-tub", "v4.0.0", "Hot Tub", "init", [spa_controller])
homie_client = homie.Client(mqtt_client, [hot_tub])

spa_client.loop_forever()
