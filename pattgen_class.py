# Pattern generator interface, this is a class file for reference on how to use pattern generator.
# The serial port connection can be initiated from the methods here.
# Script from Chin Chean, chinchean.lim@sfifteen.com

import time
from numpy import int_
import serial_device

class PattGen(serial_device.SerialDevice):
    def __init__(self, device: object = None) -> object:
        if device is None:
            try:
                device = 'COM1'
                #'/dev/ttyS2'   # set correct serial address, note the difference in Windows and Unix environment.
                # In Windows it is usually COM(x), in MAC /dev/tty.usbmodemTDC1..., in Ubuntu /dev/serial/by-id/usb-S-Fifteen_Instruments.......
                # In Linux, the path changes quite often and it is easier to just check the path by id, note line above
            except IndexError:
                print('No suitable device found!')
            self._device = device
            serial_device.SerialDevice.__init__(self, device)
            self.timeout = .1  # necessary for python2
        # check what mode is the device in

    def startport(self, port):
         self.closeport()
         serial_device.SerialDevice.__init__(self, port)

    def closeport(self):
        self._closeport()

    @property
    def idn(self):
        self._idn = int(self._getresponse('*IDN?')[0].decode().strip())
        return self._idn

    @property
    def level(self):
        self._level = int(self._getresponse('LEVEL')[0].decode().strip())
        # Input polarity：   0: NIM, 1：TTL
        return self._level

    def sendtables(self, value):
        tables = str(value)+'\n'
        self.write(tables.encode())
        print('tables loaded.')
