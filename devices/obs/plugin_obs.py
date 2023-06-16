# Rokoko, 2023

from collections import deque
import datetime
import select
import socket
from threading import Thread
import time
import simpleobsws
import asyncio

from switchboard.config import IntSetting, BoolSetting, StringSetting
from switchboard.devices.device_base import Device, DeviceStatus
from switchboard.devices.device_widget_base import DeviceWidget
from switchboard.switchboard_logging import LOGGER
import switchboard.switchboard_utils as utils


class DeviceOBS(Device):
    
    RECORDING_START_CMD_NAME = "StartRecord"
    RECORDING_STOP_CMD_NAME = "StopRecord"

    setting_obs_port = IntSetting(
        "obs_port", "OBS Port", 4455)

    setting_obs_password = StringSetting(
        "obs_password", "OBS Password", "")

    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, **kwargs)

        self.trigger_start = True
        self.trigger_stop = True

        self._slate = 'slate'
        self._take = 1

        # Stores pairs of (queued message, command name).
        self.message_queue = deque()

        self.response_status = 1
        self.last_activity = datetime.datetime.now()
        self.awaiting_echo_response = False
        self.command_response_callbacks = {
            "info": self.on_obs_echo_response,
            DeviceOBS.RECORDING_START_CMD_NAME: self.on_obs_recording_started,
            DeviceOBS.RECORDING_STOP_CMD_NAME: self.on_obs_recording_stopped}
        self.obs_connection_thread = None
        
    @staticmethod
    def plugin_settings():
        return Device.plugin_settings() + [DeviceOBS.setting_obs_port, DeviceOBS.setting_obs_password]

    def send_request_to_obs(self, request):
        """ Sends a request message to OBS's command port. """
        
        args = {}

        self.message_queue.appendleft((args, request))

    def send_echo_request(self):
        """
        Sends an echo request to OBS if not already waiting for an echo
        response.
        """
        if self.awaiting_echo_response:
            return

        if len(self.message_queue) > 0:
            return

        self.last_activity = datetime.datetime.now()
        self.awaiting_echo_response = False

    def on_obs_echo_response(self, response):
        """
        Callback that is exectued when OBS has responded to an echo request.
        """
        self.awaiting_echo_response = False

    @property
    def is_connected(self):
        return self.response_status > 0

    def connect_listener(self):
        """ Start thread with a OBS's message queue """
        
        self.last_activity = datetime.datetime.now()
        self.response_status = 1

        address = self.address if self.address is not None else "localhost"
        url = "ws://" + address + ":" + str(self.setting_obs_port.get_value())
        parameters = simpleobsws.IdentificationParameters(ignoreNonFatalRequestChecks = False) # Create an IdentificationParameters object (optional for connecting)
        
        try:
            self.client = simpleobsws.WebSocketClient(url=url, password=self.setting_obs_password.get_value(), identification_parameters = parameters)
        except Exception as e:
            LOGGER.warning("failed to open WebSocketClient!")
            LOGGER.warning(str(e))

        self.obs_connection_thread = Thread(target=self.obs_connection)
        self.obs_connection_thread.start()
        self.awaiting_echo_response = False
        self.send_echo_request()
        self.status = DeviceStatus.READY

    def disconnect_listener(self):
        self.response_status = -1
        self.status = DeviceStatus.DISCONNECTED

    async def make_connection_request(self):
        
        try:
            await self.client.connect() # Make the connection to obs-websocket
            await self.client.wait_until_identified() # Wait for the identification handshake to complete
        except Exception as e:
            LOGGER.warning('Failed - ' + str(e))
            
        try:
            request = simpleobsws.Request('GetVersion') # Build a Request object
            ret = await self.client.call(request) # Perform the request
            return ret
            
        except Exception as e:
            LOGGER.warning (str(e))

    async def make_command_request(self, cmd_name):
        return await self.client.call(simpleobsws.Request(cmd_name, None))

    async def make_disconnect_request(self):
        await self.client.disconnect() # Disconnect from the websocket server cleanly

    async def create_tasks_func():
        new_task = asyncio.create_task(make_request(self.client, self))
        await asyncio.wait(new_task)

    def obs_connection(self):
        """
        Thread procedure for sending OBS Command API post requests
        """
        ping_interval = 1.0
        disconnect_timeout = 3.0

        try:
            result = self.client.loop.run_until_complete(self.make_connection_request())

            if not result.ok():
                LOGGER.warning("OBS Connection Request failed!")
                device.response_status = 0
                device.status = DeviceStatus.CLOSED
                device.device_qt_handler.signal_device_client_disconnected.emit(device)

        except Exception as e:
            LOGGER.warning (str(e))
                
        while self.is_connected:
            try:

                if len(self.message_queue):
                    message_dict, cmd_name = self.message_queue.pop()

                    response = self.client.loop.run_until_complete(self.make_command_request(cmd_name))

                    if response.ok():
                        LOGGER.info("Response data: {}".format(response.responseData))
                        self.response_status = 200
                        self.process_message("", cmd_name)
                    else:
                        self.response_status = 0
                        self.status = DeviceStatus.CLOSED
                        self.device_qt_handler.signal_device_client_disconnected.emit(
                            self)

                else:
                    time.sleep(0.01)

                activity_delta = datetime.datetime.now() - self.last_activity

                if activity_delta.total_seconds() > disconnect_timeout:
                    raise Exception("Connection timeout")
                elif activity_delta.total_seconds() > ping_interval:
                    self.send_echo_request()

            except simpleobsws.MessageTimeout as e:
                LOGGER.warning("OBS ERROR: " + str(e))
                self.response_status = 0
                self.status = DeviceStatus.CLOSED
                self.device_qt_handler.signal_device_client_disconnected.emit(
                    self)
                break

            except Exception as e:
                LOGGER.warning(f"{self.name}: Disconnecting due to: {e}")
                self.response_status = 0
                self.status = DeviceStatus.CLOSED
                self.device_qt_handler.signal_device_client_disconnected.emit(
                    self)
                break
        self.client.loop.run_until_complete(self.make_disconnect())
        self.client = None

    def process_message(self, data, cmd_name):
        """ Processes incoming messages sent by OBS. """

        self.last_activity = datetime.datetime.now()
        
        if cmd_name in self.command_response_callbacks:
            self.command_response_callbacks[cmd_name](data)
        else:
            LOGGER.error(
                f"{self.name}: Could not find callback for "
                f"{cmd_name} request")
            assert(False)
    
    def set_slate(self, value):
        """ Notify OBS when slate name was changed. """
        self._slate = value

    def set_take(self, value):
        """ Notify OBS when Take number was changed. """
        self._take = value

    def on_obs_record_take_name_set(self, response):
        """ Callback that is executed when the take name was set in OBS. """
        pass

    def record_start(self, slate, take, description):
        """
        Called by switchboard_dialog when recording was started, will start
        recording in OBS.
        """
        if self.is_disconnected or not self.trigger_start:
            return

        self.set_slate(slate)
        self.set_take(take)

        self.send_request_to_obs(DeviceOBS.RECORDING_START_CMD_NAME)

    def on_obs_recording_started(self, response):
        """ Callback that is exectued when OBS has started recording. """
        self.record_start_confirm(self.timecode())

    def record_stop(self):
        """
        Called by switchboard_dialog when recording was stopped, will stop
        recording in OBS.
        """
        if self.is_disconnected or not self.trigger_stop:
            return

        self.send_request_to_obs(DeviceOBS.RECORDING_STOP_CMD_NAME)

    def on_obs_recording_stopped(self, response):
        """ Callback that is exectued when OBS has stopped recording. """
        self.record_stop_confirm(self.timecode(), paths=None)

    def timecode(self):
        return '00:00:00:00'

    def framerate(self):
        return '30'


class DeviceWidgetOBS(DeviceWidget):
    def __init__(self, name, device_hash, address, icons, parent=None):
        super().__init__(name, device_hash, address, icons, parent=parent)

    def _add_control_buttons(self):
        super()._add_control_buttons()
        self.trigger_start_button = self.add_control_button(
            ':/icons/images/icon_trigger_start_disabled.png',
            icon_hover=':/icons/images/icon_trigger_start_hover.png',
            icon_disabled=':/icons/images/icon_trigger_start_disabled.png',
            icon_on=':/icons/images/icon_trigger_start.png',
            icon_hover_on=':/icons/images/icon_trigger_start_hover.png',
            icon_disabled_on=':/icons/images/icon_trigger_start_disabled.png',
            tool_tip='Trigger when recording starts',
            checkable=True, checked=True)

        self.trigger_stop_button = self.add_control_button(
            ':/icons/images/icon_trigger_stop_disabled.png',
            icon_hover=':/icons/images/icon_trigger_stop_hover.png',
            icon_disabled=':/icons/images/icon_trigger_stop_disabled.png',
            icon_on=':/icons/images/icon_trigger_stop.png',
            icon_hover_on=':/icons/images/icon_trigger_stop_hover.png',
            icon_disabled_on=':/icons/images/icon_trigger_stop_disabled.png',
            tool_tip='Trigger when recording stops',
            checkable=True, checked=True)

        self.connect_button = self.add_control_button(
            ':/icons/images/icon_connect.png',
            icon_hover=':/icons/images/icon_connect_hover.png',
            icon_disabled=':/icons/images/icon_connect_disabled.png',
            icon_on=':/icons/images/icon_connected.png',
            icon_hover_on=':/icons/images/icon_connected_hover.png',
            icon_disabled_on=':/icons/images/icon_connected_disabled.png',
            tool_tip='Connect/Disconnect from listener')

        self.trigger_start_button.clicked.connect(self.trigger_start_clicked)
        self.trigger_stop_button.clicked.connect(self.trigger_stop_clicked)
        self.connect_button.clicked.connect(self.connect_button_clicked)

        # Disable the buttons
        self.trigger_start_button.setDisabled(True)
        self.trigger_stop_button.setDisabled(True)

    def trigger_start_clicked(self):
        if self.trigger_start_button.isChecked():
            self.signal_device_widget_trigger_start_toggled.emit(self, True)
        else:
            self.signal_device_widget_trigger_start_toggled.emit(self, False)

    def trigger_stop_clicked(self):
        if self.trigger_stop_button.isChecked():
            self.signal_device_widget_trigger_stop_toggled.emit(self, True)
        else:
            self.signal_device_widget_trigger_stop_toggled.emit(self, False)

    def connect_button_clicked(self):
        if self.connect_button.isChecked():
            self._connect()
        else:
            self._disconnect()

    def _connect(self):
        # Make sure the button is in the correct state
        self.connect_button.setChecked(True)

        # Enable the buttons
        self.trigger_start_button.setDisabled(False)
        self.trigger_stop_button.setDisabled(False)

        # Emit Signal to Switchboard
        self.signal_device_widget_connect.emit(self)

    def _disconnect(self):
        # Make sure the button is in the correct state
        self.connect_button.setChecked(False)

        # Disable the buttons
        self.trigger_start_button.setDisabled(True)
        self.trigger_stop_button.setDisabled(True)

        # Emit Signal to Switchboard
        self.signal_device_widget_disconnect.emit(self)
