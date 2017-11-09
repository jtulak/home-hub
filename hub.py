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
from datetime import datetime, timedelta
import pytradfri
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

    # delay between two consecutive events on one button, in milliseconds
    bouncetime = 100
    # delay before another button is accepted, in milliseconds
    sequncetime = 200
    # the minimum time a button has to be pressed to register the event, in ms
    filtertime = 5

    def __init__(self, binding, hue, tradfri):
        """ binding is a list of tuples (pin number, event) """
        self._binding = binding
        self._last_event = None
        self.hue = hue
        self.tradfri = tradfri
        self._last_event_time = datetime.now() - timedelta(hours=1)
        self._pressed_time = None
        self._pressed = None

        for (pin, event) in binding:
            print("setting up pin %d" % pin)
            GPIO.setup(pin, GPIO.IN)
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            GPIO.add_event_detect(pin, GPIO.BOTH, callback=self.callback, bouncetime=self.bouncetime)

    def pin2event(self, activated_pin):
        for (pin, event) in self._binding:
            if activated_pin == pin:
                return event
        raise ValueError("Unknown pin %d" % activated_pin)

    def callback(self, activated_pin):
        if GPIO.input(activated_pin):
            # rising edge detected
            self.callback_rising(activated_pin)
        else:
            # falling edge detected
            self.callback_falling(activated_pin)

    def callback_rising(self, activated_pin):
        """ Callback called after a button was pressed. """
        event = self.pin2event(activated_pin)
        now = datetime.now()

        if (event == self._last_event and
                timedelta(milliseconds=self.bouncetime) > (now - self._last_event_time)):
            # same event, less than bounce time, ignore
            print("event %s bounced" % event)
            return
        if (event != self._last_event and
                timedelta(milliseconds=self.sequncetime) > (now - self._last_event_time)):
            # different event, but less than sequence time, ignore
            print("event %s came too soon after the previous one, ignored" % event)
            return

        self._pressed = activated_pin
        self._pressed_time = now


    def callback_falling(self, activated_pin):
        """ Callback called after button release. """

        if self._pressed is None:
            print("release without press? wtf? pin %d" % activated_pin)
            return

        event = self.pin2event(activated_pin)
        now = datetime.now()

        if self._pressed != activated_pin:
            print("pressed (%d)/released (%d) pin mismatch? o_O"%(self._pressed, activated_pin))
            return
        if timedelta(milliseconds=self.filtertime) > (now - self._pressed_time):
            print("event %s was too short" % event)
            return

        self._last_event_time = now
        self._pressed = None
        self._last_event = event
        # GET MILLISECONDS AND COMPARE... skip event if within 300 ms or so
        # Then add a delta between up/down events and detect those events and require some holding time

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

