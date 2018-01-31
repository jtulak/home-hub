#!/usr/bin/env python3
# vim: set expandtab cindent sw=4 ts=4:
#
# (C)2018 Jan Tulak <jan@tulak.me>
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

import unittest
from unittest import mock
from src import alarm
from datetime import datetime, time


class AlarmTestCase(unittest.TestCase):
    def assertTimeEqual(self, a, b):
        """ Assert that time a and b are equal. """
        if a != b:
            raise AssertionError("{} != {}".format(a, b))


class TestAlarmTimer(AlarmTestCase):

    def setUp(self):
        alarm._log = lambda x: None

    def tearDown(self):
        pass

    def test_init_invalid_format(self):
        with self.assertRaises(SyntaxError):
            with mock.patch('src.alarm.open', mock.mock_open(read_data='bad input')) as m:
                alarm.AlarmTimer("foobar")

        with self.assertRaises(SyntaxError):
            with mock.patch('src.alarm.open', mock.mock_open(read_data='3:5')) as m:
                alarm.AlarmTimer("foobar")

    def test_init_no_file(self):
        alarm.AlarmTimer("foobar")

    def test_init_valid_format(self):
        with mock.patch('src.alarm.open', mock.mock_open(read_data='13:25')) as m:
            t = alarm.AlarmTimer("foobar")
            self.assertTimeEqual(t.time, time(13, 25))

        with mock.patch('src.alarm.open', mock.mock_open(read_data='03:05')) as m:
            t = alarm.AlarmTimer("foobar")
            self.assertTimeEqual(t.time, time(3, 5))

        with mock.patch('src.alarm.open', mock.mock_open(read_data='13:25\ndisabled')) as m:
            t = alarm.AlarmTimer("foobar")
            self.assertTimeEqual(t.time, time(13, 25))
            self.assertFalse(t.enabled)

        with mock.patch('src.alarm.open', mock.mock_open(read_data='13:25\n')) as m:
            t = alarm.AlarmTimer("foobar")
            self.assertTimeEqual(t.time, time(13, 25))
            self.assertTrue(t.enabled)

        with mock.patch('src.alarm.open', mock.mock_open(read_data='13:25\nenabled')) as m:
            t = alarm.AlarmTimer("foobar")
            self.assertTimeEqual(t.time, time(13, 25))
            self.assertTrue(t.enabled)

    def test_now(self):
        now = datetime.now().time().replace(second=0, microsecond=0)
        with mock.patch('src.alarm.open', mock.mock_open(read_data=now.strftime('%H:%M'))) as m:
            t = alarm.AlarmTimer("foobar")
            self.assertTimeEqual(t.time, now)
            self.assertTrue(t.check_now())
            t.time = t.time.replace(hour=(t.time.hour+2)%24)
            self.assertFalse(t.check_now())

    def test_set_enable(self):
        m = mock.mock_open(read_data="13:25")
        new_time = time(8, 35)
        with mock.patch('src.alarm.open', m, create=True):
            t = alarm.AlarmTimer("foobar")
            t.set_time(new_time)
            self.assertTimeEqual(t.time, new_time)
        handle = m()
        handle.write.assert_called_once_with(new_time.strftime('%H:%M\nenabled'))

    def test_set_disable(self):
        m = mock.mock_open(read_data="13:25")
        new_time = time(8, 35)
        with mock.patch('src.alarm.open', m, create=True):
            t = alarm.AlarmTimer("foobar")
            t.set_time(new_time, enabled=False)
            self.assertTimeEqual(t.time, new_time)
        handle = m()
        handle.write.assert_called_once_with(new_time.strftime('%H:%M\ndisabled'))