# Rokoko, 2023

from collections import deque
import datetime
import select
import socket
from threading import Thread
import time

from switchboard.config import IntSetting, BoolSetting
from switchboard.devices.device_base import Device, DeviceStatus
from switchboard.devices.device_widget_base import DeviceWidget
from switchboard.switchboard_logging import LOGGER
import switchboard.switchboard_utils as utils


class DeviceRokoko(Device):
    
    RECORDING_START_CMD_NAME = "CaptureStart"
    RECORDING_STOP_CMD_NAME = "CaptureStop"

    setting_rokoko_port = IntSetting(
        "rokoko_port", "Rokoko Command Port", 14047)

    setting_rokoko_enter_clip_editing = BoolSetting(
        "rokoko_enter_clip_editing", "Rokoko Enter Clip Editing", False)

    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, **kwargs)

        self.trigger_start = True
        self.trigger_stop = True

        self._slate = 'slate'
        self._take = 1

        # Stores pairs of (queued message, command name).
        self.message_queue = deque()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP

        self.response_status = 1
        self.last_activity = datetime.datetime.now()
        self.awaiting_echo_response = False
        self.command_response_callbacks = {
            "info": self.on_rokoko_echo_response,
            DeviceRokoko.RECORDING_START_CMD_NAME: self.on_rokoko_recording_started,
            DeviceRokoko.RECORDING_STOP_CMD_NAME: self.on_rokoko_recording_stopped}
        self.rokoko_connection_thread = None
        
    @staticmethod
    def plugin_settings():
        return Device.plugin_settings() + [DeviceRokoko.setting_rokoko_port, DeviceRokoko.setting_rokoko_enter_clip_editing]

    def send_request_to_rokoko(self, request):
        """ Sends a request message to Rokoko's command port. """
        
        args = {
            'command_name' : request,
            'timecode' : self.timecode(),
            'frame_rate' : self.framerate(), 
            'recording_name' : f"{self._slate} {self._take}",
            'enter_clip_editing' : self.setting_rokoko_enter_clip_editing.get_value(),
        }

        self.message_queue.appendleft((args, request))

    def send_echo_request(self):
        """
        Sends an echo request to Rokoko if not already waiting for an echo
        response.
        """
        if self.awaiting_echo_response:
            return

        if len(self.message_queue) > 0:
            return

        self.last_activity = datetime.datetime.now()
        self.awaiting_echo_response = False

    def on_rokoko_echo_response(self, response):
        """
        Callback that is exectued when Rokoko has responded to an echo request.
        """
        self.awaiting_echo_response = False

    @property
    def is_connected(self):
        return self.response_status > 0

    def connect_listener(self):
        """ Start thread with a Rokoko's message queue """
        
        self.last_activity = datetime.datetime.now()
        self.response_status = 1

        self.rokoko_connection_thread = Thread(target=self.rokoko_connection)
        self.rokoko_connection_thread.start()

        self.awaiting_echo_response = False
        self.send_echo_request()
        self.status = DeviceStatus.READY

    def disconnect_listener(self):
        self.response_status = -1
        self.status = DeviceStatus.DISCONNECTED

    def rokoko_connection(self):
        """
        Thread procedure for sending Rokoko Command API post requests
        """
        ping_interval = 1.0
        disconnect_timeout = 3.0

        while self.is_connected:
            try:

                if len(self.message_queue):
                    message_dict, cmd_name = self.message_queue.pop()

                    MESSAGE = "<{command_name}>" \
                        "<TimeCode VALUE=\"{timecode}\"/>" \
                        "<FrameRate VALUE=\"{frame_rate}\"/>" \
                        "<Name VALUE=\"{recording_name}\"/>" \
                        "<SetActiveClip VALUE=\"{enter_clip_editing}\"/>" \
                        "<ProcessID VALUE=\"12345\"/>" \
                        "</{command_name}>".format(**message_dict)

                    self.sock.sendto(bytes(MESSAGE, "utf-8"), (self.address, self.setting_rokoko_port.get_value()))

                    self.response_status = 200
                    self.process_message("", cmd_name)

                else:
                    time.sleep(0.01)

                activity_delta = datetime.datetime.now() - self.last_activity

                if activity_delta.total_seconds() > disconnect_timeout:
                    raise Exception("Connection timeout")
                elif activity_delta.total_seconds() > ping_interval:
                    self.send_echo_request()

            except Exception as e:
                LOGGER.warning(f"{self.name}: Disconnecting due to: {e}")
                self.response_status = 0
                self.status = DeviceStatus.CLOSED
                self.device_qt_handler.signal_device_client_disconnected.emit(
                    self)
                break

    def process_message(self, data, cmd_name):
        """ Processes incoming messages sent by Rokoko. """

        self.last_activity = datetime.datetime.now()
        
        if cmd_name in self.command_response_callbacks:
            self.command_response_callbacks[cmd_name](data)
        else:
            LOGGER.error(
                f"{self.name}: Could not find callback for "
                f"{cmd_name} request")
            assert(False)
    
    def set_slate(self, value):
        """ Notify Rokoko when slate name was changed. """
        self._slate = value

    def set_take(self, value):
        """ Notify Rokoko when Take number was changed. """
        self._take = value

    def on_rokoko_record_take_name_set(self, response):
        """ Callback that is executed when the take name was set in Rokoko. """
        pass

    def record_start(self, slate, take, description):
        """
        Called by switchboard_dialog when recording was started, will start
        recording in Rokoko.
        """
        if self.is_disconnected or not self.trigger_start:
            return

        self.set_slate(slate)
        self.set_take(take)

        self.send_request_to_rokoko(DeviceRokoko.RECORDING_START_CMD_NAME)

    def on_rokoko_recording_started(self, response):
        """ Callback that is exectued when Rokoko has started recording. """
        self.record_start_confirm(self.timecode())

    def record_stop(self):
        """
        Called by switchboard_dialog when recording was stopped, will stop
        recording in Rokoko.
        """
        if self.is_disconnected or not self.trigger_stop:
            return

        self.send_request_to_rokoko(DeviceRokoko.RECORDING_STOP_CMD_NAME)

    def on_rokoko_recording_stopped(self, response):
        """ Callback that is exectued when Rokoko has stopped recording. """
        self.record_stop_confirm(self.timecode(), paths=None)

    def timecode(self):
        return '00:00:00:00'

    def framerate(self):
        return '30'


class DeviceWidgetRokoko(DeviceWidget):
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
