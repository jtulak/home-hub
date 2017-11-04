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

HUE = None
TRADFRI = None

def main():
    global HUE, TRADFRI
    try:
        HUE = Hue.autoinit()
        TRADFRI = Tradfri.autoinit(HUE)
        HUE.set_tradfri(TRADFRI)
    except HuefriException:
        # message is already printed
        sys.exit(1)
    except pytradfri.error.ClientError as e:
        print("An error occured when initializing Tradfri: %s" % str(e))
        sys.exit(1)

    # bind GPIO pins
    c = Controller([
        (12, onoff),
        (13, up),
        (19, down),
        (5, right),
        (6, left),
        (26, off),
        (20, on),
        ])
    """
        Forever check the main light and update Hue lights.
    """
    try:
        while True:
            try:
                TRADFRI.update()
                HUE.update()
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
        sys.exit(0)


def up(pin):
    print("up")
    HUE.brightness_inc()
    TRADFRI.brightness_inc()

def down(pin):
    print("down")
    HUE.brightness_dec()
    TRADFRI.brightness_dec()

def left(pin):
    print("left")
    HUE.color_prev()
    TRADFRI.color_prev()

def right(pin):
    print("right")
    HUE.color_next()
    TRADFRI.color_next()

def onoff(pin):
    print("onoff")
    if TRADFRI.state:
        off(pin)
    else:
        on(pin)

def on(pin):
    print("on")
    HUE.set_brightness(255)
    TRADFRI.set_brightness(255)

def off(pin):
    print("off")
    HUE.set_brightness(0)
    TRADFRI.set_brightness(0)

class Controller(object):
    def __init__(self, binding):
        """ binding is a list of tuples (pin number, callback) """
        self._binding = binding
        for (pin, callback) in binding:
            print("setting up pin %d" % pin)
            GPIO.setup(pin, GPIO.IN)
            GPIO.add_event_detect(pin, GPIO.RISING, callback=callback, bouncetime=200)



if __name__ == '__main__':
    main()

