#!/usr/bin/env python3
import asyncio
import datetime
import logging
from operator import attrgetter
import paho.mqtt.client as mqtt
import pybalboa
from sys import argv

import pyhomie

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def on_homie_message(msg):
    logger.debug("Message received on topic: " + str(msg.topic))

logger.debug("Starting Spa client...")
channel = None if len(argv) < 2 else int(argv[1])
spa_client = pybalboa.clients.SerialClient("/dev/ttyUSB0", channel)
spa_client.log.setLevel(logging.DEBUG)

spa_controller = pybalboa.homie.Node(spa_client, "spa-controller", "Balboa Spa Controller", "spa")
spa_controller.on_message = on_homie_message
hot_tub = pyhomie.Device("hot-tub", "Hot Tub", nodes=[spa_controller])
homie_client = pyhomie.Client("balboa", [hot_tub])
homie_client.connect("bass")

asyncio.get_event_loop().run_forever()
