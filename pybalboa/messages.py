class Message(object):
    DELIMETER = 0x7e
    def __init__(self, msg_type, payload=bytes()):
        self._type = msg_type
        self._payload = payload

    def __bytes__(self):
        b = bytes([1 + len(self.type) + len(self.payload) + 1]) + self.type + self.payload
        return bytes([self.DELIMETER]) + b + bytes([Message.crc(b), self.DELIMETER])

    def __len__(self):
        return bytes(self)[1]

    @property
    def type(self):
        return self._type

    @property
    def payload(self):
        return self._payload

    @staticmethod
    def crc(data):
        """
        Calculate the checksum byte for a balboa message
        * Generated on Sun Apr  2 10:09:58 2017,
        * by pycrc v0.9, https://pycrc.org
        * using the configuration:
        *    Width         = 8
        *    Poly          = 0x07
        *    Xor_In        = 0x02
        *    ReflectIn     = False
        *    Xor_Out       = 0x02
        *    ReflectOut    = False
        *    Algorithm     = bit-by-bit

        https://github.com/garbled1/gnhast/blob/master/balboacoll/collector.c
        """
        crc = 0xb5
        for cur in range(len(data)):
            for i in range(8):
                bit = crc & 0x80
                crc = ((crc << 1) & 0xff) | ((data[cur] >> (7 - i)) & 0x01)
                if (bit):
                    crc = crc ^ 0x07
            crc &= 0xff
        for i in range(8):
            bit = crc & 0x80
            crc = (crc << 1) & 0xff
            if bit:
             crc ^= 0x07
        return crc ^ 0x02

    @staticmethod
    def from_bytes(b):
        b = bytes(b)
        if b[0] != Message.DELIMETER or b[-1] != Message.DELIMETER:
            raise ValueError("Message must start and end with Message.DELIMETER")
        b = b[1:-1]
        if len(b) < 5 or b[0] != len(b):
            raise ValueError("Invalid Message length")
        if b[-1] != Message.crc(b[:-1]):
            raise ValueError("Invalid Message checksum")
        return Message(b[1:4], b[4:-1])


class ReadyMessage(Message):
    def __init__(self):
        super().__init__(bytes([0x10, 0xbf, 0x06]))


class StatusMessage(Message):
    def __init__(self, *, priming_mode, current_temperature, hours, minutes, heating_mode, temperature_scale, time_mode, heating_status, temperature_range, pump_status, circ_pump, light_status, set_temperature):
        super().__init__(bytes([0xff, 0xaf, 0x13]), bytes(
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
                ((time_mode & 0x1) << 1) + (temperature_scale & 0x1),
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

    @staticmethod
    def from_bytes(b):
        msg = Message.from_bytes(b)
        if len(msg) != 28:
            raise ValueError("StatusMessages are 28 bytes long")
        if msg.type != bytes([0xff, 0xaf, 0x13]):
            raise ValueError("Invalid StatusMessage header")
        b = msg.payload
        return StatusMessage(
            priming_mode=b[1] & 0x1,
            current_temperature=b[2],
            hours=b[3],
            minutes=b[4],
            heating_mode=b[5] & 0x3,
            time_mode=(b[9] & 0x1) >> 1,
            temperature_scale=b[9] & 0x1,
            heating_status=(b[10] & 0x3) >> 4,
            temperature_range=b[10] & 0x2,
            pump_status=b[11],
            circ_pump=b[13],
            light_status=b[14],
            set_temperature=b[20]
        )

class ConfigurationRequest(Message):
    def __init__(self):
        super().__init__(bytes([0x0a, 0xbf, 0x04]))


class FilterConfigurationRequest(Message):
    def __init__(self):
        super().__init__(bytes([0x0a, 0xbf, 0x22]), bytes([0xba, 0x00, 0xbb]))


class ToggleItemRequest(Message):
    def __init__(self, item):
        super().__init__(bytes([0x0a, 0xbf, 0x11]), bytes([item, 0x00]))


class TogglePump1Request(ToggleItemRequest):
    def __init__(self):
        super().__init__(0x04)


class TogglePump2Request(ToggleItemRequest):
    def __init__(self):
        super().__init__(0x05)


class TogglePump3Request(ToggleItemRequest):
    def __init__(self):
        super().__init__(0x06)


class TogglePump4Request(ToggleItemRequest):
    def __init__(self):
        super().__init__(0x07)


class ToggleLight1Request(ToggleItemRequest):
    def __init__(self):
        super().__init__(0x11)


class ToggleLight2Request(ToggleItemRequest):
    def __init__(self):
        super().__init__(0x12)


class ToggleTemperatureRangeRequest(ToggleItemRequest):
    def __init__(self):
        super().__init__(0x50)


class ToggleHeatingModeRequest(ToggleItemRequest):
    def __init__(self):
        super().__init__(0x51)


class SetTemperatureRequest(Message):
    def __init__(self, temperature):
        super().__init__(bytes([0x0a, 0xbf, 0x20]), bytes([temperature]))

    @property
    def temperture(self):
        return bytes(self)[5]


class SetTemperatureScaleRequest(Message):
    FAHRENHEIT = 0x00
    CELSIUS    = 0x01
    def __init__(self, scale):
        scale = int(scale)
        if scale != SetTemperatureScaleRequest.FAHRENHEIT or scale != SetTemperatureScaleRequest.CELSIUS:
            raise ValueError("Invalid Temperature Scale")
        super().__init__(bytes([0x0a, 0xbf, 0x27]), bytes([scale]))

    @property
    def scale(self):
        return bytes(self)[5]


class SetTimeRequest(Message):
    MODE_12HR = 0
    MODE_24HR = 1
    def __init__(self, t=None, mode=0):
        if t is None:
            t = datetime.datetime.now()
        if not instanceof(t, datetime.datetime):
            raise ValueError("Invalid datetime")
        mode = int(mode)
        if mode != SetTimeRequest.MODE_12HR or mode != SetTimeRequest.MODE_24HR:
            raise ValueError("Invalid mode")
        super().__init__(bytes([0x0a, 0xbf, 0x21]), bytes([(mode << 7) + t.hours, t.minutes]))

    @property
    def hours(self):
        return bytes(self)[5] & 0x7F

    @property
    def minutes(self):
        return bytes(self)[6]

    @property
    def mode(self):
        return bytes(self) >> 7


class BalboaSpaLocalController:
    def __init__(self, dev):
        import serial
        self._s = serial.Serial(dev, baudrate=115200)

    def loop_forever(self):
        while True:
            msg = self.recv()
            self.onmessage(msg)

    def onmessage(self, msg):
        print("hi")
        pass

    def recv(self):
        while True:
            b = self._s.read_until(bytes([Message.DELIMETER]))
            b += self._s.read_until(bytes([Message.DELIMETER]))
            try:
                msg = Message.from_bytes(b)
            except ValueError as e:
                continue
            return msg

    def send(self, msg):
        while True:
            try:
                ReadyMessage.from_bytes(self.recv())
            except ValueError:
                continue
            return self._s.write(bytes(msg))
