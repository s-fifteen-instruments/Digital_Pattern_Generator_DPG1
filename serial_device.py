from __future__ import print_function  # Needed for compatibility with Py2
"""
Author: Alessandro Cere
Modified by: Chin Chean Lim, 03/06/2019
Created: 2017.10.16

Description:
General serial device
"""
import serial
import time

from serial import SerialException


class SerialDevice(serial.Serial):
    """
    The usb device is seen as an object through this class,
    inherited from the generic serial one.
    """

    def __init__(self, device_path=None, timeout=0.2):
        """
        Initializes the USB device.
        It requires the full path to the serial device as arguments
        """
        try:
            serial.Serial.__init__(self, device_path, timeout)
            self.timeout = timeout
            self.baudrate = 115200
            self.stopbits = serial.STOPBITS_ONE
            self.bytesize = serial.EIGHTBITS
            self.parity = serial.PARITY_NONE
            self._reset_buffers()
        except SerialException:
            print('Connection failed')

    def _closeport(self):
        self.close()

    def _reset_buffers(self):
        self.reset_input_buffer()
        self.reset_output_buffer()

    def _getresponse(self, cmd):
        self._reset_buffers()
        self.write((cmd + '\n').encode())
        return self.readlines()

    # This function is for the timestamp TDC device.
    def _getresponseTime(self, cmd, t_sleep):
        # this function bypass the termination character (since there is none for timestamp mode), streams data from device for the integration time.
        self._reset_buffers()
        self.write((cmd + '\n').encode())
        memory = b''
        time0 = time.time()
        while (time.time() - time0 < t_sleep):  # Stream data for duration of integration time plus some delay set in usbcount_class.
            Buffer_length = self.in_waiting
            memory = memory + self.read(Buffer_length)
        Rlength = len(memory)
        print(str(Rlength) + " Bytes Recorded")
        return memory

    def help(self):
        """
        Prints device help to the screen
        """
        ([print(x.decode().strip()) for x in self._getresponse('help')])
