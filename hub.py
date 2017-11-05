#!/usr/bin/env python3
# vim: set expandtab cindent sw=4 ts=4:
#
# (C)2017 Jan Tulak <jan@tulak.me>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import time
import sys
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

import huefri
from huefri.common import Config
from huefri.common import HuefriException
from huefri.common import log
from huefri.common import COLORS_MAP
from huefri.hue import Hue
from huefri.tradfri import Tradfri


def main():
    try:
        hue = Hue.autoinit()
        tradfri = Tradfri.autoinit(hue)
        hue.set_tradfri(tradfri)
    except HuefriException:
        # message is already printed
        sys.exit(1)
    except pytradfri.error.ClientError as e:
        print("An error occured when initializing Tradfri: %s" % str(e))
        sys.exit(1)

    # bind GPIO pins
    c = Controller([
        (12, 'onoff'),
        (13, 'up'),
        (19, 'down'),
        (5,  'right'),
        (6,  'left'),
        (26, 'off'),
        (20, 'on'),
        ], hue=hue, tradfri=tradfri)
    """
        Forever check the main light and update Hue lights.
    """
    try:
        while True:
            try:
                tradfri.update()
                hue.update()
            except pytradfri.error.RequestTimeout:
                """ This exception is raised here and there and doesn't cause anything.
                    So print just a short notice, not a full stacktrace.
                """
                log("MAIN", "Tradfri RequestTimeout().")
            except Exception as err:
                traceback.print_exc()
                log("MAIN", err)
            time.sleep(1)
    except KeyboardInterrupt:
        log("MAIN", "Exiting on ^c.")
        GPIO.cleanup()
        sys.exit(0)


class Controller(object):
    def __init__(self, binding, hue, tradfri):
        """ binding is a list of tuples (pin number, event) """
        self._binding = binding
        self.hue = hue
        self.tradfri = tradfri
        for (pin, event) in binding:
            print("setting up pin %d" % pin)
            GPIO.setup(pin, GPIO.IN)
            GPIO.add_event_detect(pin, GPIO.RISING, callback=self.callback, bouncetime=200)

    def pin2event(self, activated_pin):
        for (pin, event) in self._binding:
            if activated_pin == pin:
                return event
        raise ValueError("Unknown pin %d" % activated_pin)


    def callback(self, activated_pin):
        event = self.pin2event(activated_pin)
        if event == 'up':
            self.up()
        elif event == 'down':
            self.down()
        elif event == 'left':
            self.left()
        elif event == 'right':
            self.right()
        elif event == 'on':
            self.on()
        elif event == 'off':
            self.off()
        elif event == 'onoff':
            self.onoff()
        else:
            raise ValueError("Unknown event '%s' for known pin %d" % (event, activated_pin))


    def up(self):
        print("up")
        self.hue.brightness_inc()
        self.tradfri.brightness_inc()

    def down(self):
        print("down")
        self.hue.brightness_dec()
        self.tradfri.brightness_dec()

    def left(self):
        print("left")
        self.hue.color_prev()
        self.tradfri.color_prev()

    def right(self):
        print("right")
        self.hue.color_next()
        self.tradfri.color_next()

    def onoff(self):
        print("onoff")
        if self.tradfri.state:
            self.off()
        else:
            self.on()

    def on(self):
        print("on")
        self.hue.set_brightness(255)
        self.tradfri.set_brightness(255)

    def off(self):
        print("off")
        self.hue.set_brightness(0)
        self.tradfri.set_brightness(0)



if __name__ == '__main__':
    main()

