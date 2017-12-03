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
GPIO.setmode(GPIO.BCM)

import huefri
from huefri.common import Config
from huefri.common import HuefriException
from huefri.common import log
from huefri.hue import Hue
from huefri.tradfri import Tradfri

from src.controller import Controller
from src.alarm import Alarm

def main():
    initialized = False
    Config.path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "config.json")
    c = None
    try:
        while True:
            try:
                if not initialized:
                    # bind GPIO pins
                    c = Controller(Config, [
                        (12, 'onoff'),
                        (13, 'up'),
                        (19, 'down'),
                        (5,  'right'),
                        (6,  'left'),
                        (26, 'off'),
                        (20, 'on'),
                        ])
                    initialized = True
                else:
                    c.update()
            except pytradfri.error.ClientError as ex:
                print("An error occured with Tradfri: %s" % str(ex))
            except pytradfri.error.RequestTimeout:
                """ This exception is raised here and there and doesn't cause anything.
                    So print just a short notice, not a full stacktrace.
                """
                log("MAIN", "Tradfri request timeout, retrying...")
            except huefri.common.BadConfigPathError as ex:
                print("An error occured with configuration: %s" % str(ex))
                sys.exit(1)

            except Exception as err:
                traceback.print_exc()
                log("MAIN", err)
            time.sleep(1)
    except KeyboardInterrupt:
        log("MAIN", "Exiting on ^c.")
        c.cleanup()
        sys.exit(0)

if __name__ == '__main__':
    main()
