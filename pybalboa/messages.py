#!/usr/bin/env python3
import datetime
from enum import IntEnum, unique
import re
import struct

class Message(object):

    BROADCAST_CHANNEL = 0xFF
    CRC_TABLE = [ # Polynomial = 0x07
        0x00, 0x07, 0x0e, 0x09, 0x1c, 0x1b, 0x12, 0x15, 0x38, 0x3f, 0x36, 0x31, 0x24, 0x23, 0x2a, 0x2d,
        0x70, 0x77, 0x7e, 0x79, 0x6c, 0x6b, 0x62, 0x65, 0x48, 0x4f, 0x46, 0x41, 0x54, 0x53, 0x5a, 0x5d,
        0xe0, 0xe7, 0xee, 0xe9, 0xfc, 0xfb, 0xf2, 0xf5, 0xd8, 0xdf, 0xd6, 0xd1, 0xc4, 0xc3, 0xca, 0xcd,
        0x90, 0x97, 0x9e, 0x99, 0x8c, 0x8b, 0x82, 0x85, 0xa8, 0xaf, 0xa6, 0xa1, 0xb4, 0xb3, 0xba, 0xbd,
        0xc7, 0xc0, 0xc9, 0xce, 0xdb, 0xdc, 0xd5, 0xd2, 0xff, 0xf8, 0xf1, 0xf6, 0xe3, 0xe4, 0xed, 0xea,
        0xb7, 0xb0, 0xb9, 0xbe, 0xab, 0xac, 0xa5, 0xa2, 0x8f, 0x88, 0x81, 0x86, 0x93, 0x94, 0x9d, 0x9a,
        0x27, 0x20, 0x29, 0x2e, 0x3b, 0x3c, 0x35, 0x32, 0x1f, 0x18, 0x11, 0x16, 0x03, 0x04, 0x0d, 0x0a,
        0x57, 0x50, 0x59, 0x5e, 0x4b, 0x4c, 0x45, 0x42, 0x6f, 0x68, 0x61, 0x66, 0x73, 0x74, 0x7d, 0x7a,
        0x89, 0x8e, 0x87, 0x80, 0x95, 0x92, 0x9b, 0x9c, 0xb1, 0xb6, 0xbf, 0xb8, 0xad, 0xaa, 0xa3, 0xa4,
        0xf9, 0xfe, 0xf7, 0xf0, 0xe5, 0xe2, 0xeb, 0xec, 0xc1, 0xc6, 0xcf, 0xc8, 0xdd, 0xda, 0xd3, 0xd4,
        0x69, 0x6e, 0x67, 0x60, 0x75, 0x72, 0x7b, 0x7c, 0x51, 0x56, 0x5f, 0x58, 0x4d, 0x4a, 0x43, 0x44,
        0x19, 0x1e, 0x17, 0x10, 0x05, 0x02, 0x0b, 0x0c, 0x21, 0x26, 0x2f, 0x28, 0x3d, 0x3a, 0x33, 0x34,
        0x4e, 0x49, 0x40, 0x47, 0x52, 0x55, 0x5c, 0x5b, 0x76, 0x71, 0x78, 0x7f, 0x6a, 0x6d, 0x64, 0x63,
        0x3e, 0x39, 0x30, 0x37, 0x22, 0x25, 0x2c, 0x2b, 0x06, 0x01, 0x08, 0x0f, 0x1a, 0x1d, 0x14, 0x13,
        0xae, 0xa9, 0xa0, 0xa7, 0xb2, 0xb5, 0xbc, 0xbb, 0x96, 0x91, 0x98, 0x9f, 0x8a, 0x8d, 0x84, 0x83,
        0xde, 0xd9, 0xd0, 0xd7, 0xc2, 0xc5, 0xcc, 0xcb, 0xe6, 0xe1, 0xe8, 0xef, 0xfa, 0xfd, 0xf4, 0xf3
    ];

    DELIMITER = 0x7e

    def __init__(self, *, channel, type_code, arguments=bytes()):
        self.channel = channel
        self.type_code = type_code
        self.arguments = arguments

    def __bytes__(self):
        b = bytes([len(self.arguments) + 5])
        b += bytes([self.channel])
        b += bytes([0xAF if self.channel == self.BROADCAST_CHANNEL else 0xBF])
        b += bytes([self.type_code])
        b += self.arguments
        return bytes([self.DELIMITER]) + b + bytes([Message.crc(b), self.DELIMITER])

    def __iter__(self):
        self._cursor = 0
        return self

    def __len__(self):
        return bytes(self)[1]

    def __next__(self):
        if self._cursor >= len(bytes(self)):
            raise StopIteration
        b = bytes(self)[self._cursor]
        self._cursor += 1
        return b

    @staticmethod
    def crc(data):
        crc = 0x02; # XOR In
        for b in data:
            crc = ((Message.CRC_TABLE[(crc ^ b) & 0xff] ^ (crc << 8)) & 0xff)
        return crc ^ 0x02 # XOR Out

    @classmethod
    def from_bytes(cls, b):
        b = bytes(b)
        if b[0] != Message.DELIMITER or b[-1] != Message.DELIMITER:
            raise ValueError("Messages must start and end with Message.DELIMITER")
        b = b[1:-1]
        if len(b) < 5 or b[0] != len(b) or (hasattr(cls, "LENGTH") and b[0] != cls.LENGTH):
            raise ValueError("Invalid length for " + cls.__name__)
        if hasattr(cls, "CHANNEL") and b[1] != cls.CHANNEL:
            raise ValueError("Invalid channel for " + cls.__name__)
        if hasattr(cls, "TYPE_CODE") and b[3] != cls.TYPE_CODE:
            raise ValueError("Invalid message type code for " + cls.__name__)
        if b[-1] != cls.crc(b[:-1]):
            raise ValueError("Invalid checksum")
        return Message(channel=b[1], type_code=b[3], arguments=b[4:-1])


class NewClientClearToSend(Message):

    TYPE_CODE = 0x00
    LENGTH = 5
    CHANNEL = 0xFE

    def __init__(self):
        super().__init__(type_code=self.TYPE, channel=self.CHANNEL)

    @classmethod
    def from_bytes(cls, b):
        msg = super().from_bytes(b)
        return NewClientClearToSend()


class ChannelAssignmentRequest(Message):

    TYPE_CODE = 0x01
    CHANNEL = 0xFE
    LENGTH = 8

    def __init__(self, arguments):
        super().__init__(type_code=self.TYPE_CODE, channel=self.CHANNEL, arguments=arguments)


class ChannelAssignmentResponse(Message):

    TYPE_CODE = 0x02
    CHANNEL = 0xFE
    LENGTH = 8

    def _init__(self, arguments):
        super()._init__(type_code=self.TYPE_CODE, channel=self.CHANNEL, arguments=arguments)


class ChannelAssignmentAcknowlegement(Message):

    TYPE_CODE = 0x03
    LENGTH = 5

    def __init__(self, channel):
        super().__init__(type_code=self.TYPE_CODE, channel=channel)


class ExistingClientRequest(Message):

    TYPE_CODE = 0x04
    LENGTH = 5

    def __init__(self, channel):
        super().__init__(type_code=self.TYPE_CODE, channel=channel)


class ExistingClientResponse(Message):

    TYPE_CODE = 0x05
    LENGTH = 0x08

    def __init__(self, channel, arguments):
         super().__init__(type_code=self.TYPE_CODE, channel=channel, arguments=arguments)


class ClientClearToSend(Message):

    TYPE_CODE = 0x06
    LENGTH = 5

    def __init__(self, channel):
        super().__init__(type_code=self.TYPE_CODE, channel=channel)

    @classmethod
    def from_bytes(cls, b):
        msg = super().from_bytes(b)
        return ClientClearToSend(msg.channel)


class NothingToSend(Message):

    TYPE_CODE = 0x07
    LENGTH = 5

    def __init__(self, channel):
        super().__init__(type_code=self.TYPE_CODE, channel=channel)

    @classmethod
    def from_bytes(cls, b):
        msg = super().from_bytes(b)
        return NothingToSend(channel=msg.channel)


class ToggleItemRequest(Message):

    TYPE_CODE = 0x11
    LENGTH = 7

    @unique
    class ItemCode(IntEnum):
        PRIMING_MODE = 0x01
        PUMP_1 = 0x04
        PUMP_2 = 0x05
        PUMP_3 = 0x06
        PUMP_4 = 0x07
        PUMP_5 = 0x08
        PUMP_6 = 0x09
        BLOWER = 0x0C
        MISTER = 0x0E
        LIGHT_1 = 0x11
        LIGHT_2 = 0x12
        AUX_1 = 0x16
        AUX_2 = 0x17
        HOLD_MODE = 0x3C
        TEMPERATURE_RANGE = 0x50
        HEAT_MODE = 0x51

    def __init__(self, channel, item):
        super().__init__(type_code=self.TYPE_CODE, channel=channel, arguments=bytes([item, 0x00]))


class StatusUpdate(Message):

    TYPE_CODE = 0x13
    LENGTH = 28
    CHANNEL = 0xFF

    def __init__(self, *, priming_mode, current_temperature, hours, minutes, heating_mode, filter_mode, temperature_scale, time_mode, heating_status, temperature_range, pump_status, circ_pump, light_status, set_temperature):
        super().__init__(type_code=self.TYPE_CODE, channel=self.CHANNEL, arguments=bytes(
            [
                0x00,
                priming_mode & 0x1,
                current_temperature,
                hours,
                minutes,
                heating_mode & 0x3,
                0x00,
                0x00,
                0x00,
                ((filter_mode & 0x3) << 2) + ((time_mode & 0x1) << 1) + (temperature_scale & 0x1),
                ((heating_status & 0x3) << 4) + (temperature_range & 0x1) << 3,
                pump_status,
                0x00,
                (circ_pump & 0x1) << 1,
                ((light_status & 0x1) << 1) + (light_status & 0x1),
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                set_temperature,
                0x00,
                0x00
            ])
        )

    @property
    def priming_mode(self):
        return self.payload[1] & 0x1

    @property
    def current_temperature(self):
        return self.payload[2]

    @property
    def hours(self):
        return self.payload[3]

    @property
    def minutes(self):
        return self.payload[4]

    @property
    def heating_mode(self):
        return self.payload[5] & 0x03

    @property
    def time_mode(self):
        return (self.payload[9] >> 1) & 0x1

    @property
    def temperature_scale(self):
        return self.payload[9] & 0x1

    @property
    def heating_status(self):
        return (self.payload[10] >> 4) & 0x3

    @property
    def temperature_range(self):
        return (self.payload[10] >> 3) & 0x1

    @property
    def pump_status(self):
        return self.payload[11]

    @property
    def circ_pump(self):
        return (self.payload[13] >> 1) & 0x1

    @property
    def light_status(self):
        return self.payload[14] & 0x3

    @property
    def set_temperature(self):
        return self.payload[20]

    @classmethod
    def from_bytes(cls, b):
        msg = super().from_bytes(b)
        b = msg.arguments
        return StatusUpdate(
            priming_mode=b[1] & 0x1,
            current_temperature=b[2],
            hours=b[3],
            minutes=b[4],
            heating_mode=b[5] & 0x3,
            filter_mode=(b[9] & 0xc) >> 2,
            time_mode=(b[9] & 0x1) >> 1,
            temperature_scale=b[9] & 0x1,
            heating_status=(b[10] & 0x3) >> 4,
            temperature_range=b[10] & 0x2,
            pump_status=b[11],
            circ_pump=b[13],
            light_status=b[14],
            set_temperature=b[20]
        )


class SetTemperatureRequest(Message):

    TYPE_CODE = 0x20
    LENGTH = 6

    def __init__(self, channel, temperature):
        super().__init__(type_code=self.TYPE_CODE, channel=channel, arguments=bytes([temperature]))

    @property
    def temperture(self):
        return bytes(self)[5]


class SetTimeRequest(Message):

    TYPE_CODE = 0x21
    LENGTH = 7

    CLOCK_MODE_12HR = 0
    CLOCK_MODE_24HR = 1

    def __init__(self, channel, t=None, mode=0):
        if t is None:
            t = datetime.datetime.now().time()
        if not isinstance(t, datetime.time):
            raise ValueError("Invalid time")
        if t.tzinfo is not None:
            t = (datetime.datetime.combine(datetime.date.today(), t) + t.utcoffset()).time()
        mode = int(mode)
        if mode not in [SetTimeRequest.CLOCK_MODE_12HR, SetTimeRequest.CLOCK_MODE_24HR]:
            raise ValueError("Invalid mode")
        super().__init__(type_code=self.TYPE_CODE, channel=channel, arguments=bytes([(mode << 7) + t.hour, t.minute]))

    @property
    def hours(self):
        return bytes(self)[5] & 0x7F

    @property
    def minutes(self):
        return bytes(self)[6]

    @property
    def mode(self):
        return bytes(self) >> 7


class SettingsRequest(Message):

    TYPE_CODE = 0x22
    LENGTH = 8

    def __init__(self, channel, arguments):
        super().__init__(type_code=self.TYPE_CODE, channel=channel, arguments=arguments)


class FilterCyclesRequest(SettingsRequest):

    def __init__(self, channel):
        super().__init__(channel, bytes([0x01, 0x00, 0x00]))

    @classmethod
    def from_bytes(cls, b):
        msg = super().from_bytes(b)
        if msg.payload != bytes([0x01, 0x00, 0x00]):
            raise ValueError
        return FilterCyclesRequest(msg.channel)


class InformationRequest(SettingsRequest):

    def __init__(self, channel):
        super().__init__(channel, bytes([0x02, 0x00, 0x00]))

    @classmethod
    def from_bytes(cls, b):
        msg = super().from_bytes(b)
        if msg.payload != bytes([0x02, 0x00, 0x00]):
            raise ValueError
        return InformationRequest(msg.channel)


class PreferencesRequest(SettingsRequest):

    def __init__(self, channel):
        super().__init__(channel, bytes([0x08, 0x00, 0x00]))

    @classmethod
    def from_bytes(cls, b):
        msg = super().from_bytes(b)
        if msg.payload != bytes([0x08, 0x00, 0x00]):
            raise ValueError
        return InformationRequest(msg.channel)


class FaultLogRequest(SettingsRequest):

    def __init__(self, channel, entry=0xFF):
        super().__init__(channel, bytes([0x20, entry, 0x00]))

    @classmethod
    def from_bytes(cls, b):
        msg = super().from_bytes(b)
        b = msg.payload
        if b[0] != 0x20 or b[2] != 0x00:
            raise ValueError
        return FaultLogRequest(msg.channel, msg.payload[1])


class FilterCyclesMessage(Message):

    TYPE_CODE = 0x23
    LENGTH = 13

    def __init__(self, channel, start1: datetime.time, duration1: datetime.timedelta, *, start2: datetime.time=None, duration2: datetime.timedelta=None):
        duration1h = duration1.seconds // 3600
        duration1m = (duration1.seconds - duration1h * 3600) // 60
        if start2 is not None and duration2 is not None:
            start2h = 0x80 + start2.hour
            start2m = start2.minute
            duration2h = duration2.seconds // 3600
            duration2m = (duration2.seconds - duration1h * 3600) // 60
        else:
            start2h = 0
            start2m = 0
            duration2h = 0
            duration2m = 0
        super().__init__(type_code=self.TYPE_CODE, channel=channel, arguments=bytes([
            start1.hour,
            start1.minute,
            duration1h,
            duration1m,
            start2h,
            start2m,
            duration2h,
            duration2m
        ]))

    @property
    def start1(self):
        b = self.arguments
        return datetime.time(b[0], b[1])

    @property
    def duration1(self):
        b = self.arguments
        return datetime.timedelta(0, b[2] * 3600 + b[3] * 60)

    @property
    def start2(self):
        b = self.arguments
        if b[4] & 0x80:
            return datetime.time(b[4] & 0x7F, b[5])
        return None

    @property
    def duration2(self):
        b = self.arguments
        if b[4] & 0x80:
            return datetime.timedelta(0, b[6] * 3600 + b[7] * 60)
        return None

    @classmethod
    def from_bytes(cls, b):
        msg = super().from_bytes(b)
        b = msg.payload
        print("hello" + cls.__name__)
        if b[4] & 0x80:
            start2 = datetime.time(b[4] & 0x7F, b[5])
            duration2 = datetime.timedelta(0, b[6] * 3600 + b[7] * 60)
        else:
            start2 = None
            duration2 = None
        return cls(msg.channel,
            datetime.time(b[0], b[1]),
            datetime.timedelta(0, b[2] * 3600 + b[3] * 60),
            start2=start2,
            duration2=duration2
        )


class FilterCyclesResponse(FilterCyclesMessage):
    pass


class SetFilterCyclesRequest(FilterCyclesMessage):
    pass


class InformationResponse(Message):

    TYPE_CODE = 0x24
    LENGTH = 26

    def __init__(self, *, channel, ssid, model, setup, cfg_signature, heater_voltage, heater_type, dip_sw):
        b = bytearray(21)
        p = re.compile("^M(\d+)_(\d+) V(\d+)(\.(\d+))?$")
        m = p.match(ssid)
        b[0] = int(m.group(1))
        b[1] = int(m.group(2))
        b[2] = int(m.group(3))
        b[3] = 0 if m.group(4) is None else int(m.group(4))
        b[4:12] = model.encode("ascii").ljust(8)
        b[12] = setup
        b[13:17] = struct.pack(">I", cfg_signature)
        b[17] = 0x01 if heater_voltage == 220 else 0x00
        b[18] = heater_type
        b[19:21] = struct.pack(">H", dip_sw)
        print(",".join(map("{:02X}".format, b)))
        super().__init__(type_code=self.TYPE_CODE, channel=channel, arguments=bytes(b))

    @classmethod
    def from_bytes(cls, b):
        msg = super().from_bytes(b)
        b = msg.payload
        return InformationResponse(
            ssid="M" + str(b[0]) + "_" + str(b[1]) + " V" + str(b[2]) + ("" if b[3] == 0 else "." + str(b[3])),
            model=b[4:12].decode("ascii"),
            setup=b[12],
            cfg_signature=struct.unpack(">I", b[13:17])[0],
            heater_voltage=220 if b[17] == 0x01 else 120,
            heater_type=b[18],
            dip_sw=struct.unpack(">H", b[19:21])[0]
        )


class PreferencesResponse(Message):

    TYPE_CODE = 0x26
    LENGTH = 23

    def __init__(self, channel, arguments):
        super().__init__(type_code=self.TYPE_CODE, channel=channel, arguments=arguments)


class SetPreferenceRequest(Message):

    TYPE_CODE = 0x27
    LENGTH = 7

    @unique
    class PreferenceCode(IntEnum):
        REMINDERS = 0x00
        TEMPERATURE_SCALE = 0x01
        CLOCK_MODE = 0x02
        CLEANUP_CYCLE = 0x03
        DOLPHIN_ADDRESS = 0x04
        M8_AI = 0x06

    def __init__(self, channel, code, value):
        super().__init__(type_code=self.TYPE_CODE, channel=channel, arguments=bytes([code, value]))


class SetTemperatureScaleRequest(SetPreferenceRequest):

    FAHRENHEIT = 0x00
    CELSIUS    = 0x01

    def __init__(self, channel, scale):
        scale = int(scale)
        if scale != SetTemperatureScaleRequest.FAHRENHEIT and scale != SetTemperatureScaleRequest.CELSIUS:
            raise ValueError("Invalid Temperature Scale")
        super().__init__(channel, super().PreferenceCode.TEMPERATURE_SCALE, scale)

    @property
    def scale(self):
        return bytes(self)[5]


class SetClockModeRequest(SetPreferenceRequest):

    MODE_12_HOUR = 0x00
    MODE_24_HOUR = 0x01

    def __init__(self, channel, mode):
        mode = int(mode)
        if mode != SetClockModeRequest.MODE_12_HOUR and scale != SetClockModeRequest.MODE_24_HOUR:
            raise ValueError("Invalid Clock Mode")
        super().__init__(channel, super().PreferenceCode.CLOCK_MODE, mode)


class FaultLogResponse(Message):

    TYPE_CODE = 0x28
    LENGTH = 15

    MESSAGES = { # Per TP900 User Guide
        15: "Sensors are out of sync",
        16: "The water flow is low",
        17: "The water flow has failed",
        18: "The settings have been reset",
        19: "Priming Mode",
        20: "The clock has failed",
        21: "The settings have been reset",
        22: "Program memory failure",
        26: "Sensors are out of sync -- Call for service",
        27: "The heater is dry",
        28: "The heater may be dry",
        29: "The water is too hot",
        30: "The heater is too hot",
        31: "Sensor A Fault",
        32: "Sensor B Fault",
        34: "A pump may be stuck on",
        35: "Hot fault",
        36: "The GFCI test failed",
        37: "Hold Mode"
    }

    def __init__(self, *, channel, count, entry, message_code, days_ago, hours, minutes, flags, set_temperature, sensor_a_temperature, sensor_b_temperature):
        b = bytearray(10)
        b[0] = count
        b[1] = entry
        b[2] = message_code
        b[3] = days_ago
        b[4] = hours
        b[5] = minutes
        b[6] = flags
        b[7] = set_temperature
        b[8] = sensor_a_temperature
        b[9] = sensor_b_temperature
        super().__init__(type_code=self.TYPE_CODE, channel=channel, arguments=bytes(b))

    @property
    def entry(self):
        return self.payload[1] + 1

    @classmethod
    def from_bytes(cls, b):
        msg = super().from_bytes(b)
        b = msg.payload
        return FaultLogResponse(
            count=b[0],
            entry=b[1],
            message_code=b[2],
            days_ago=b[3],
            hours=b[4],
            minutes=b[5],
            flags=b[6],
            set_temperature=b[7],
            sensor_a_temperature=b[8],
            sensor_b_temperature=b[9]
        )


class ConfigurationResponse(Message):

    TYPE_CODE = 0x2E
    LENGTH = 11

    def __init__(self, channel, cfg):
        super().__init__(type_code=self.TYPE_CODE, channel=channel, arguments=cfg)

    @classmethod
    def from_bytes(cls, b):
        msg = super().from_bytes(b)
        return ConfigurationResponse(msg.channel, msg.arguments)
