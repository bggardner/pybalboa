import datetime
from enum import Enum, unique
import isodate
import logging
import paho.mqtt.client

import pyhomie

import pybalboa.clients as clients
import pybalboa.messages as messages

class Node(pyhomie.Node):

    def __init__(self, balboa_client: clients.Client, id, name, type):
        # TODO: Query spa for configuration and assign properties accordingly
        properties = []

        # Byte string properties
        properties.append(pyhomie.Property("status", "Status", "string"))
        properties.append(pyhomie.Property("information", "Information", "string"))
        properties.append(pyhomie.Property("filter-cycles", "Filter Cycles", "string"))
        properties.append(pyhomie.Property("configuraiton", "Status", "string"))

        # Properties in Status Update:
        properties.append(pyhomie.Property("priming", "Priming", "boolean"))
        properties.append(pyhomie.Property("current-temperature", "Current Temperature", "float"))
        properties.append(TimeProperty("time", "Time"))
        properties.append(Property("heating-mode", "Heating Mode", "enum", format="ready,rest,ready-in-rest", settable=True))
        properties.append(TemperatureScaleProperty("temperature-scale", "Temperature Scale"))
        properties.append(ClockModeProperty("clock-mode", "Clock Mode"))
        properties.append(pyhomie.Property("heating", "heating", "boolean"))
        properties.append(pyhomie.Property("circulation-pump", "Circulation Pump", "boolean"))
        properties.append(SetTemperatureProperty("set-temperature", "Set Temperature"))
        # TODO: Change pump formats to boolean/enum if 1-speed or 2-speed
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.PUMP_2, "pump-1", "Pump 1", "enum", format="off,low,high"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.PUMP_2, "pump-2", "Pump 2", "enum", format="off,low,high"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.PUMP_3, "pump-3", "Pump 3", "enum", format="off,low,high"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.PUMP_4, "pump-4", "Pump 4", "enum", format="off,low,high"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.PUMP_5, "pump-5", "Pump 5", "enum", format="off,low,high"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.PUMP_6, "pump-6", "Pump 6", "enum", format="off,low,high"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.BLOWER, "blower", "Blower", "boolean"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.MISTER, "mister", "Mister", "boolean"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.LIGHT_1, "light-1", "Light 1", "boolean"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.LIGHT_2, "light-2", "Light 2", "boolean"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.AUX_1, "aux-1", "Aux 1", "boolean"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.AUX_2, "aux-2", "Aux 2", "boolean"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.HOLD_MODE, "hold-mode", "Hold Mode", "boolean"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.TEMPERATURE_RANGE, "temperature-range", "Temperature Range", "enum", format="low,high"))
        properties.append(ToggleItemProperty(messages.ToggleItemRequest.ItemCode.HEAT_MODE, "heat-mode", "Temperature Range", "enum", format="ready,rest"))

        super().__init__(id, name, type, properties)
        self.balboa_client = balboa_client
        self.balboa_client.on_message = self.on_balboa_message

    def connect(self, device):
        super().connect(device)
        self.balboa_client.request_configuration()
        self.balboa_client.request_information()
        self.balboa_client.request_filter_cycles()
        self.device.publish("$state", "ready")

    def on_balboa_message(self, msg: messages.Message):
        if self.device is None:
            return
        if msg.type_code == messages.StatusUpdate.TYPE_CODE:
            self.publish("status", "".join(map("{:02X}".format, msg.arguments)))
            if msg.arguments[11] & 0x03 == 0:
                self.properties["pump-1"].value = "off"
            elif msg.arguments[11] & 0x03 == 1:
                self.properties["pump-1"].value = "low"
            else:
                self.properties["pump-1"].value = "high"
            if msg.arguments[11] & 0x0C == 0:
                self.properties["pump-2"].value = "off"
            elif msg.arguments[11] & 0x0C == 0x04:
                self.properties["pump-2"].value = "low"
            else:
                self.properties["pump-2"].value = "high"
            if msg.arguments[11] & 0x30 == 0:
                self.properties["pump-3"].value = "off"
            elif msg.arguments[11] & 0x30 == 0x10:
                self.properties["pump-3"].value = "low"
            else:
                self.properties["pump-3"].value = "high"
            if msg.arguments[11] & 0xC0 == 0:
                self.properties["pump-4"].value = "off"
            elif msg.arguments[11] & 0xC0 == 0x40:
                self.properties["pump-4"].value = "low"
            else:
                self.properties["pump-4"].value = "high"
            if msg.arguments[2] == 0xFF:
                self.properties["current-temperature"] = None
            else:
                if self.properties["temperature-scale"].value == "Celsius":
                    self.properties["current-temperature"] = float(msg.arguments[2]) / 2
                else:
                    self.properties["current-temperature"] = float(msg.arguments[2])
            self.properties["time"].value = datetime.datetime.combine(datetime.date.today(), datetime.time(msg.arguments[3], msg.arguments[4]))
            if msg.arguments[5] == 0:
                self.properties["heating-mode"].value = "ready"
            if msg.arguments[5] == 1:
                self.properties["heating-mode"].value = "rest"
            if msg.arguments[5] == 3:
                self.properties["heating-mode"].value = "ready-in-rest"
            self.properties["circulation-pump"].value = msg.arguments[13] & 0x02 == 0x02
            self.properties["blower"].value = msg.arguments[13] & 0xC0 == 0xC0
            self.properties["light-1"].value = msg.arguments[14] & 0x03 == 0x03
            self.properties["light-2"].value = msg.arguments[14] & 0x0C == 0x0C
            self.properties["set-temperature"].value = msg.arguments[20]
        elif msg.type_code == messages.FilterCyclesResponse.TYPE_CODE:
            self.publish("filter-cycles", "".join(map("{:02X}".format, msg.arguments)))
        elif msg.type_code == messages.InformationResponse.TYPE_CODE:
            self.publish("information", "".join(map("{:02X}".format, msg.arguments)))
        elif msg.type_code == messages.PreferencesResponse.TYPE_CODE:
            self.publish("preferences", "".join(map("{:02X}".format, msg.arguments)))
        elif msg.type_code == messages.ConfigurationResponse.TYPE_CODE:
            self.publish("configuration", "".join(map("{:02X}".format, msg.arguments)))


class Property(pyhomie.Property):

    @property
    def balboa_client(self):
        return self.node.balboa_client


class ClockModeProperty(Property):

    def __init__(self, id, name):
        super().__init__(id, name, "enum", format="12-hour,24-hour", settable=True)

    def _on_message(self, msg: paho.mqtt.client.MQTTMessage):
        if msg.topic == "set":
            self.balboa_client.set_preference(
               messages.SetPreferenceRequest.PreferenceCode.CLOCK_MODE,
                messages.SetClockModeRequest.MODE_24_HOUR if msg.payload.decode("utf-8") == "24-hour" else messages.SetClockModeRequest.MODE_12_HOUR
            )
        else:
            super()._on_message(msg)


class SetTemperatureProperty(Property):

    def __init__(self, id, name):
        super().__init__(id, name, "float", settable=True)

    def _on_message(self, msg: paho.mqtt.client.MQTTMessage):
        if msg.topic == "set":
            t = float(msg.payload.decode("utf-8"))
            if self.node.properties["temperature-scale"].value == "Celsius":
                t *= 2
            self.balboa_client.set_temperature(int(t))
        else:
            super()._on_message()


class TemperatureScaleProperty(Property):

    def __init__(self, id, name):
        super().__init__(id, name, "enum", format="Fahrenheit,Celsius", settable=True)

    def _on_message(self, msg: paho.mqtt.client.MQTTMessage):
        if msg.topic == "set":
            self.balboa_client.set_preference(
                messages.SetPreferenceRequest.PreferenceCode.TEMPERATURE_SCALE,
                messages.SetTemperatureScaleRequest.CELSIUS if msg.payload.decode("utf-8") == "Celsius" else messages.SetTemperatureScaleRequest.FAHRENHEIT
            )
        else:
            super()._on_message()


class TimeProperty(Property):

    def __init__(self, id, name):
        super().__init__(id, name, "datetime", settable=True)

    def _on_message(self, msg: paho.mqtt.client.MQTTMessage):
        if msg.topic == "set":
            self.balboa_client.set_time(isodate.parse_datetime(msg.payload.decode("utf-8")).timetz())
        else:
            super()._on_message(msg)


class ToggleItemProperty(Property):

    def __init__(self, item_code, id, name, data_type, format=None):
        self.item_code = item_code
        super().__init__(id, name, "boolean", settable=True, retained=True)

    def _on_message(self, msg: paho.mqtt.client.MQTTMessage):
        if msg.topic == "set":
            self.balboa_client.toggle_item(self.item_code)
        else:
            super()._on_message(msg)
