import asyncio
import datetime
import logging
import queue
import time
from socket import error as SocketError

import pybalboa.messages as messages

class Client:

    def __init__(self, channel=None):
        self.channel = channel
        self.log = logging.getLogger(__name__)
        self.queue = queue.Queue()
        self._channel_timeout = None
        if channel is not None:
            self._channel_timeout = time.time() + 10
        asyncio.ensure_future(self.listen())

    async def listen(self):
        while True:
            msg = await self.recv()
            self._on_message_internal(msg)
            self.on_message(msg)

    def _on_message_internal(self, msg: messages.Message):
        if self.channel is None:
            if msg.type_code == messages.NewClientClearToSend.TYPE_CODE:
                self.log.debug("Requesting channel...")
                self._send_internal(messages.ChannelAssignmentRequest(bytes([0x02, 0xF1, 0x73]))); # TODO: Determine meaning of these bytes (probably unique)
            elif msg.type_code == messages.ChannelAssignmentResponse.TYPE_CODE:
                self.channel = msg.arguments[0];
                self.log.debug("Acknowledging assignment to channel {}".format(self.channel))
                self._send_internal(messages.ChannelAssignmentAcknowlegement(self.channel))
        elif msg.channel == self.channel:
            if msg.type_code == messages.ExistingClientRequest.TYPE_CODE:
                self._send_internal(messages.ExistingClientResponse(self.channel, bytes([0x04, 0x08, 0x00])))
            elif msg.type_code == messages.ClientClearToSend.TYPE_CODE:
                if self.queue.empty():
                    self._send_internal(messages.NothingToSend(self.channel))
                else:
                    msg = self.queue.get()
                    if msg.channel is None:
                        msg.channel = self.channel
                    self._send_internal(msg)
                    self.log.debug(msg.__class__.__name__ + " sent on channel {}".format(msg.channel))
            self._channel_timeout = None
        elif self._channel_timeout is not None:
            if time.time() > self._channel_timeout:
                self.log.error("No Client Clear to Send detected on channel {}, client will only listen.".format(self.channel))
                self._channel_timeout = None

    def on_message(self, msg: messages.Message):
        pass

    async def recv(self):
        raise NotImplementedError()

    def request_configuration(self):
        self.request_settings(bytes([0x00, 0x00, 0x01]))

    def request_filter_cycles(self):
        self.request_settings(bytes([0x01, 0x00, 0x00]))

    def request_information(self):
        self.request_settings(bytes([0x02, 0x00, 0x00]))

    def request_settings(self, settings_code):
        self.send(messages.SettingsRequest(self.channel, settings_code))

    def send(self, msg: messages.Message):
        self.queue.put(msg)
        self.log.debug(msg.__class__.__name__ + " queued on channel {}".format(msg.channel))

    def _send_internal(self, msg: messages.Message):
        raise NotImplementedError()

    def set_filter_cycles(self, start1: datetime.time, duration1: datetime.timedelta, *, start2: datetime.time=None, duration2: datetime.timedelta=None):
        self.send(messages.SetFilterCyclesRequest(self.channel,
            start1,
            duration1,
            start2=start2,
            duration2=duration2
        ))

    def set_preference(self, code: messages.SetPreferenceRequest.PreferenceCode, value):
        self.send(messages.SetPreferenceRequest(self.channel, code, value))

    def set_temperature(self, t):
        self.send(messages.SetTemperatureRequest(self.channel, t))

    def set_time(self, t):
        self.send(messages.SetTimeRequest(self.channel, t))

    def toggle_item(self, item):
        self.send(messages.ToggleItemRequest(self.channel, item))

    def toggle_light(self, n):
        if n in [1, 2]:
            item_code = messages.ToggleItemRequest.ItemCode.LIGHT_1 + (n - 1)
            msg = messages.ToggleItemRequest(self.channel, item_code)
        else:
            raise NotImplementedError()
        self.send(msg)

    def toggle_pump(self, n):
        if n in [1, 2, 3, 4, 5, 6]:
            item_code = messages.ToggleItemRequest.ItemCode.PUMP_1 + (n - 1)
            msg = messages.ToggleItemRequest(self.channel, item_code)
        else:
            raise NotImplementedError()
        self.send(msg)


class SerialClient(Client):

    def __init__(self, dev, channel=None):
        import serial
        super().__init__(channel)
        self._s = serial.Serial(dev, baudrate=115200)

    async def recv(self):
        import serial
        while True:
            try:
                b = self._s.read_until(bytes([messages.Message.DELIMITER])) # Start of message
                b += self._s.read(1) # Read in length
                if b[1] == messages.Message.DELIMITER: # Check if first read was actually end of previous message
                    b = b[1:2] + self._s.read(1) # Drop first delimiter, read in length
                b += self._s.read(b[1]) # Read rest of message
            except serial.serialutil.SerialException as e:
                self.log.error(e);
                time.sleep(1) # Errors are usually recoverable after waiting
                continue
            try:
                msg = messages.Message.from_bytes(b)
            except ValueError:
                continue
            return msg

    def _send_internal(self, msg):
        self._s.write(bytes(msg))


class TcpClient(Client):

    DEFAULT_CHANNEL = 0x0A
    DEFAULT_PORT = 4257

    def __init__(self, host, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.connected = False
        asyncio.get_event_loop().run_until_complete(self.connect())
        asyncio.get_event_loop().run_until_complete(self.check_connection())
        super().__init__(self.DEFAULT_CHANNEL)

    async def connect(self):
        """ Connect to the spa."""
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        except (asyncio.TimeoutError, ConnectionRefusedError):
            self.log.error("Cannot connect to spa at {0}:{1}".format(self.host, self.port))
            return False
        self.connected = True
        return True

    async def check_connection(self):
        """ Set this up to periodically check the spa connection and fix. """
        while True:
            if not self.connected:
                self.log.error("Lost connection to spa, attempting reconnect.")
                await self.connect()
            await asyncio.sleep(10)

    async def disconnect(self):
        """ Stop talking to the spa."""
        self.log.info("Disconnect requested")
        self.connected = False
        self.writer.close()
        await self.writer.wait_closed()

    async def recv(self):
        while True:
            if not self.connected:
                await asyncio.sleep(1)
                continue
            try:
                header = await self.reader.readexactly(2)
            except SocketError as err:
                if err.errno == errno.ECONNRESET:
                    self.log.error('Connection reset by peer')
                    self.connected = False
                if err.errno == errno.EHOSTUNREACH:
                    self.log.error('Spa unreachable')
                    self.connected = False
                else:
                    self.log.error('Spa socket error: {0}'.format(str(err)))
                continue
            except Exception as e:
                self.log.error('Spa read failed: {0}'.format(str(e)))
                continue

            if header[0] == messages.Message.DELIMITER:
                # header[1] is size, + checksum + messages.Message.DELIMITER (we already read 2 tho!)
                rlen = header[1]
            else:
                continue

            # now get the rest of the data
            try:
                data = await self.reader.readexactly(rlen)
            except Exception as e:
                self.log.error('Spa read failed: {0}'.format(str(e)))
                continue

            full_data = header + data
            try:
                msg = messages.Message.from_bytes(full_data)
            except ValueError:
                continue
            return msg

    def _send_internal(self, msg):
        if not self.connected:
            return
        self.writer.write(bytes(msg))
        asyncio.get_event_loop().run_until_complete(self.writer.drain())
