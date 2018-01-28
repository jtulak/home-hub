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
import datetime
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
    "gpio": False,
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

def _log(msg):
    log("MAIN", msg)

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
    last_reboot = datetime.datetime.now()
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

                # reboot at 4 am every day, to get around some issues with long-running
                # gateway
                now = datetime.datetime.now()
                if now.hour == 4 and ((now - last_reboot).seconds/3600) > 5:
                    _log("Time for reboot of Tradfri gateway...")
                    c.tradfri.reboot()
                    c.cleanup()
                    initialized = False
                    time.sleep(10)
                    last_reboot = now

            except pytradfri.error.ClientError as ex:
                _log("An error occured with Tradfri: %s" % str(ex))

            except pytradfri.error.RequestTimeout:
                """ This exception is raised here and there and doesn't cause anything.
                    So _log just a short notice, not a full stacktrace.
                """
                _log("Tradfri request timeout, retrying...")

            except (KeyError, huefri.common.BadConfigPathError) as ex:
                _log("An error occured with configuration: %s" % str(ex))
                _log("The config file should look like:\n%s" % CFG_EXAMPLE)
                sys.exit(1)

            #except USR1Exception:
            #    _log("USR1 captured")
            #    last_reboot = datetime.datetime(year=2006, month=5, day=15)

            except IndexError as err:
                _log(err)
                _log("reinitializing")
                c.cleanup()
                initialized = False

            except Exception as err:
                traceback.print_exc()
                _log(err)

    except KeyboardInterrupt:
        print("Exiting on ^c.")
        c.cleanup()
        sys.exit(0)

if __name__ == '__main__':
    main()
