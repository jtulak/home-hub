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
import os
import traceback
import pytradfri
import RPi.GPIO as GPIO
import signal

import huefri
from huefri.common import Config
from huefri.common import HuefriException
from huefri.common import log
from huefri.hue import Hue
from huefri.tradfri import Tradfri

from src.controller import Controller
from src.alarm import Alarm

CFG_EXAMPLE = """{
"alarm": {
	"sound": {
		"path": "beep.mp3",
		"volume_increment": 10,
		"volume_initial": 10,
		"force_alsa": true
	} ,
	"brightening": {
		"duration": 1,
		"step": 1,
	},
},
"tradfri":{
	"addr": "tradfri",
	"secret": "XXXXXXXXX",
	"controlled": [0],
	"main": 0
	}
}
"""


class USR1Exception(Exception):
    pass

def onsig1(a, b):
    raise USR1Exception()

def main():
    initialized = False
    signal.signal(signal.SIGUSR1,onsig1)
    Config.path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "config.json")
    c = None
    alarm = None
    try:
        while True:
            try:
                time.sleep(1)
                if not initialized:
                    # bind GPIO pins
                    c = Controller(Config, [
                        (12, 'onoff'),
                        (13, 'alarm'),
                        (19, 'down'),
                        (5,  'right'),
                        (6,  'left'),
                        (26, 'off'),
                        (20, 'on'),
                        (21, 'alarm'),
                        ])
                    alarm = Alarm(Config, c)
                    initialized = True
                else:
                    c.update()
                    alarm.alarm()

            except pytradfri.error.ClientError as ex:
                print("An error occured with Tradfri: %s" % str(ex))

            except pytradfri.error.RequestTimeout:
                """ This exception is raised here and there and doesn't cause anything.
                    So print just a short notice, not a full stacktrace.
                """
                log("MAIN", "Tradfri request timeout, retrying...")

            except (KeyError, huefri.common.BadConfigPathError) as ex:
                print("An error occured with configuration: %s" % str(ex))
                print("The config file should look like:\n%s" % CFG_EXAMPLE)
                sys.exit(1)

            except USR1Exception:
                log("MAIN", "USR1 captured")
                log("MAIN", "reinitializing")
                c.cleanup()
                initialized = False

            except IndexError as err:
                log("MAIN", err)
                log("MAIN", "reinitializing")
                c.cleanup()
                initialized = False

            except Exception as err:
                traceback.print_exc()
                log("MAIN", err)

    except KeyboardInterrupt:
        log("MAIN", "Exiting on ^c.")
        c.cleanup()
        sys.exit(0)

if __name__ == '__main__':
    main()
