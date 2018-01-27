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
from datetime import datetime, timedelta
import RPi.GPIO as GPIO

from huefri.hue import Hue
from huefri.tradfri import Tradfri

class Controller(object):

    # delay between two consecutive events on one button, in milliseconds
    bouncetime = 100
    # delay before another button is accepted, in milliseconds
    sequncetime = 200
    # the minimum time a button has to be pressed to register the event, in ms
    filtertime = 5

    # If set to a callable object/function, it will be called before any operation
    # after button release. The standard callback will continue only when this
    # function returns true
    callback_condition = None

    def __init__(self, config, binding):
        """ binding is a list of tuples (pin number, event) """
        try:
            self.hue = Hue.autoinit(config)
        except KeyError:
            # missing hue config part, try to continue without it
            self.hue = None
        try:
            self.tradfri = Tradfri.autoinit(config, self.hue)
        except KeyError:
            # missing tradfri config part, try to continue without it
            self.tradfri = None

        if self.hue is not None:
            self.hue.set_tradfri(self.tradfri)
        elif self.tradfri is not None:
            self.tradfri.set_hue(None)
        else:
            raise ValueError("You have to have at least one hub configured in your configuration file.")

        self._last_event_time = datetime.now() - timedelta(hours=1)
        self._binding = binding
        self._last_event = None
        self._pressed_time = None
        self._pressed = None
        self.alarm_start = False
        self.prev_brightness = 0

        GPIO.setmode(GPIO.BCM)
        for (pin, event) in binding:
            print("setting up pin %d" % pin)
            GPIO.setup(pin, GPIO.IN)
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            GPIO.add_event_detect(pin, GPIO.BOTH, callback=self.callback, bouncetime=self.bouncetime)

    def cleanup(self):
        GPIO.cleanup()


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
        print("RISING %d" % activated_pin)
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

        print("FALLING %d" % activated_pin)
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

        if callable(self.callback_condition):
            if not self.callback_condition():
                print("Callback interrupted by condition.")
                return

        try:
            event(self)
        except TypeError:
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
            elif event == 'alarm':
                print("Alarm signal")
                self.alarm_start = True
            else:
                raise ValueError("Unknown event '%s' for known pin %d" % (event, activated_pin))


    def update(self):
        """ Get updated info from tradfri and hue """
        if self.tradfri:
            self.tradfri.changed()
        if self.hue:
            self.hue.changed()

    def set_brightness(self, brightness):
        """ Set all connected bulbs to given brightness """
        if self.hue is not None:
            self.hue.set_brightness(brightness)
        if self.tradfri is not None:
            self.tradfri.set_brightness(brightness)
        self.prev_brightness = brightness

    def get_brigtnesses(self):
        """ Return a list of current brigthnesses on all connected lights """
        brightnesses = list()
        if self.hue is not None:
            for light in self.hue.lights_selected:
                brightnesses.append(self.hue.bridge.lights[light]()['state']['bri'])

        if self.tradfri is not None:
            for light in self.tradfri.lights_selected:
                br = self.tradfri._lights[light].light_control.lights[0].dimmer
                if not self.tradfri._lights[light].light_control.lights[0].state:
                    br = 0
                brightnesses.append(br)

        return brightnesses

    def up(self):
        print("up")
        if self.hue:
            self.hue.brightness_inc()
        if self.tradfri:
            self.tradfri.brightness_inc()

    def down(self):
        print("down")
        if self.hue:
            self.hue.brightness_dec()
        if self.tradfri:
            self.tradfri.brightness_dec()

    def left(self):
        print("left")
        if self.hue:
            self.hue.color_prev()
        if self.tradfri:
            self.tradfri.color_prev()

    def right(self):
        print("right")
        if self.hue:
            self.hue.color_next()
        if self.tradfri:
            self.tradfri.color_next()

    def onoff(self):
        print("onoff")
        if self.tradfri.state:
            self.off()
        else:
            self.on()

    def on(self):
        print("on")
        if self.hue:
            self.hue.set_brightness(255)
        if self.tradfri:
            self.tradfri.set_brightness(255)

    def off(self):
        print("off")
        if self.hue:
            self.hue.set_brightness(0)
        if self.tradfri:
            self.tradfri.set_brightness(0)
