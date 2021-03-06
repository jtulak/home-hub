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
from datetime import datetime, timedelta, time
import pytradfri
import sys
import vlc
import re
import os

import huefri
from huefri.common import Config
from huefri.common import HuefriException
from huefri.common import log
from huefri.common import COLORS_MAP
from huefri.hue import Hue
from huefri.tradfri import Tradfri

SOUND = None # do not set

def _log(msg):
    log("Alarm", msg)


class Sound(object):
    def __init__(self, cnf):
        self.path = cnf['path']
        self.volume_increment = cnf['volume_increment']
        if cnf['force_alsa']:
            vlc_inst = vlc.Instance('--input-repeat=-1', '--aout=alsa')
        else:
            vlc_inst = vlc.Instance('--input-repeat=-1')
        vlc_med = vlc_inst.media_new(self.path)
        self.player = vlc_inst.media_player_new()
        self.player.set_media(vlc_med)
        self._volume = cnf['volume_initial']
        self._volume_starting = cnf['volume_initial']

    def volume_reset(self):
        self.volume = self._volume_starting

    def volume_update(self):
        if self.is_playing() and self.volume < 100:
            self.volume += self.volume_increment

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        if value > 100:
            value = 100
        elif value < 0:
            value = 0

        self._volume = value
        _log("set volume to %d" % value)
        self.player.audio_set_volume(value)

    def is_playing(self):
        return self.player.is_playing()

    def play(self):
        self.volume_reset()
        self.player.play()
        _log("playing %s" % self.path)


    def stop(self):
        self.volume_reset()
        self.player.stop()
        _log("Stop playing %s" % self.path)

class Queue(object):
    """ A fifo queue implementation that drops old items if it gets over max_size """
    def __init__(self, max_size=0):
        self.max_size = max_size
        self.data = []
        self.items = 0

    def full(self):
        """ Return True if the queue is at its max capacity """
        return self.max_size and self.max_size == self.items

    def put(self, item):
        """ Put a new item into the top of the queue """
        if self.full():
            self.pop()
        self.data.append(item)
        self.items += 1

    def pop(self):
        """ Pop an item from the bottom of the queue """
        if self.items:
            self.items -= 1
        return self.data.pop(0)

    def flush(self):
        """ Drop all data """
        self.data = []
        self.items = 0

    def __iter__(self):
        for i in self.data:
            yield i


class Alarm(object):
    br_max = 254 # max brightness value
    ALARM_FILE = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), '..',
            "alarm_time")

    def __init__(self, config, controller):
        global SOUND

        cnf = config.get()['alarm']
        self.controller = controller
        self.gpio = cnf['gpio']
        self.step = cnf['brightening']['step']
        self.duration_sec = cnf['brightening']['duration']
        self.duration = round(self.duration_sec / self.step)
        self.alarm_started = None
        SOUND = Sound(cnf['sound'])
        self.sound = SOUND
        self.timer = AlarmTimer(self.ALARM_FILE)
        self.prev_brightness = Queue(max_size=5)

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

    def brightness_changed(self):
        """ Return True if any light is different from expected value """
        # first check if there was a change
        brs = self.controller.get_brigtnesses()
        potential_change = False
        for br in brs:
            if br != self.controller.prev_brightness:
                potential_change = True
        # then filter out this change if it is just a timeout issue
        # if the brightnesses are all within the list of the last few values we send,
        # then ignore this change
        if potential_change:
            for br in brs:
                if not br in self.prev_brightness:
                    return True
        return False

    def check_time(self):
        """ Return True if the alarm should start now """
        return self.timer.check_now()

    def alarm(self):
        """ Main alarm function. Do one step, watch for interrupts. """
        def callback_condition():
            global SOUND
            if SOUND.is_playing():
                SOUND.stop()
                return False
            return True

        self.sound.volume_update()
        if (self.gpio and self.controller.alarm_start or self.check_time()) and \
            self.alarm_started is None and self.timer.enabled:
            # this block will run just once, when the alarm is starting
            self.alarm_started = datetime.now()
            self.controller.prev_brightness = 0
            self.prev_brightness.flush()
            _log("Should run alarm")

        if not self.alarm_started:
            if self.brightness_changed():
                callback_condition()
            return

        delta = round((datetime.now() - self.alarm_started).total_seconds() / self.step)
        if delta > self.duration + 1:
            # alarm ended
            self.controller.callback_condition = callback_condition
            self.controller.alarm_start = False
            self.alarm_started = None
            self.sound.play()
            _log("Alarm ending")
            return

        if self.brightness_changed():
            _log("Unexpected brightness value. Current {}, prev {}".format(
                self.controller.get_brigtnesses(), self.controller.prev_brightness
            ))
            self.controller.alarm_start = False
            self.alarm_started = None
            _log("Alarm aborted")
            return

        brightness = self.compute_brightness(delta)
        if brightness != self.controller.prev_brightness:
            _log("setting up brightness: %d" % brightness)
            self.prev_brightness.put(brightness)
            self.controller.set_brightness(brightness)


class AlarmTimer(object):
    """ An object encapsulating the set up alarm time operations. """
    check_delta = timedelta(seconds=30)

    def __init__(self, path : str):
        """ Argument path: path to the file with set up time """
        self.path = path
        self.enabled = False
        self.load_file()
        self.last_check = datetime.now()
        if self.time is None:
            _log("No file with time exists. ({})".format(self.path))

    def get_time(self):
        """ Get the time the alarm is set to """
        return self.time

    def load_file(self):
        """ Load the set up time form a file (path given to __init__) """
        def syntax_error(reason):
            return SyntaxError("Alarm file {} could not be parsed: {}".format(self.path, reason))

        try:
            with open(self.path, 'r') as f:
                # read time
                line = f.readline().strip()
                if not re.match('[0-9][0-9]:[0-9][0-9]', line):
                    raise syntax_error("Can't parse the time on line 0: '{}'".format(line))
                self.time = datetime.strptime(line, '%H:%M').time()

                # try to read enabled/disabled
                line = f.readline().strip()
                if line == "disabled":
                    self.enabled = False
                elif line == "enabled" or line == '':
                    self.enabled = True
                else:
                    raise syntax_error("There is a garbage on line 1: '{}'".format(line))

        except FileNotFoundError:
            self.time = None
        except ValueError as ex:
            raise SyntaxError("Alarm file {} could not be parsed. Error: '{}'\nFile content: '{}'".format(self.path, ex, line))

    def check_now(self):
        """ Check if now is the set up time. Check the configured time once in a time. """
        if self.last_check + self.check_delta < datetime.now() or not self.time:
            self.load_file()

        if self.time is None:
            return False
        return self.time == datetime.now().time().replace(second=0, microsecond=0)

    def set_time(self, when:time, enabled:bool=True):
        """ Write new time to the file """
        self.time = when
        with open(self.path, 'w') as f:
            f.write('{time}\n{enabled}\n'.format(
                time = self.time.strftime('%H:%M'),
                enabled = 'enabled' if enabled else 'disabled'
            ))