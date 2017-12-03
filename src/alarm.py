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

import huefri
from huefri.common import Config
from huefri.common import HuefriException
from huefri.common import log
from huefri.common import COLORS_MAP
from huefri.hue import Hue
from huefri.tradfri import Tradfri


class Alarm(object):
    br_max = 254 # max brightness value

    def __init__(self, controller, step = 10, duration_sec = 300):
        self.controller = controller
        self.duration = round(duration_sec / step)
        self.step = step
        self.duration_sec = duration_sec

    def compute_brightness(self, delta):
        """ Compute what should be the brightness at any given time """
        if delta <= 0:
            return 0
        
        # brightness gain of one step
        step = self.br_max / self.duration
        # how many steps since the start
        brightness = round(delta * step)

        if brightness > self.br_max:
            brightness = self.br_max

        return brightness

    def should_abort(self):
        """ Return True if any light is different from expected value """
        brs = self.controller.get_brigtnesses()

        for br in brs:
            if br != self.controller.prev_brightness:
                return True

        return False

    def alarm(self):
        """ Main alarm function. Do one step, watch for interrupts. """
        if self.controller.alarm_start and self.controller.alarm_started is None:
            # this block will run just once, when the alarm is starting
            self.controller.alarm_started = datetime.now()
            print("Should run alarm")
        
        if not self.controller.alarm_started:
            return

        delta = round((datetime.now() - self.controller.alarm_started).total_seconds() / self.step)

        if delta > self.duration + 1:
            # alarm ended
            self.controller.alarm_start = False
            self.controller.alarm_started = None
            self.controller.prev_brightness = 0
            print("Alarm ending")
            return

        if self.should_abort():
            self.controller.alarm_start = False
            self.controller.alarm_started = None
            self.controller.prev_brightness = 0
            print("Alarm aborted")
            return

        brightness = self.compute_brightness(delta)
        print("setting up brightness: %d" % brightness)
        self.controller.set_brightness(brightness)