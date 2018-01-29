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

# An example of usage:
# g = WebGUI(os.path.join(
#                     os.path.dirname(os.path.realpath(__file__)), '..',
#                     "alarm_time"))
# g.run() # will fork into background
#
# while True:
#     _log('foo')
#     time.sleep(3)

from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from datetime import datetime
from urllib.parse import unquote
from multiprocessing import Process
from src.alarm import AlarmTimer
from huefri.common import log

__all__ = ["WebGUI"]

def _log(msg):
    log("WebGUI", msg)

# HTTPRequestHandler class
class AlarmHTTPServer_RequestHandler(BaseHTTPRequestHandler):
    """ HTTP request handler modified for alarm """

    templater = None
    handler = None
    template_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), 'webgui.html')

    def _set_headers(self):
        """ Send http headers """
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()


    def _send_body(self, data={}):
        """ Send the body itself """
        # Send message back to client
        with open(self.template_path, 'r') as f:
            message = f.read()

        if self.templater:
            message = self.templater(message, data=data)

        # Write content as utf-8 data
        self.wfile.write(bytes(message, "utf8"))

    def _get_post_data(self):
        """ Return a dict with POST data, empty dict if no data present """
        content_length = int(self.headers['Content-Length'])
        post_data_raw = unquote(self.rfile.read(content_length).decode("utf-8"))

        data = {}
        for line in post_data_raw.split('\n'):
            key, val = line.split('=')
            data[key] = val
        _log('Got POST data: {}'.format(data))
        return data

    def do_POST(self):
        """ Handle a POST request """
        data = self._get_post_data()
        new_time = datetime.strptime(data['time'], '%H:%M').time()
        self.handler(new_time=new_time)

        self._set_headers()
        self._send_body({'MESSAGE': "New time was saved"})

    def do_HEAD(self):
        """ Handle a HEAD request """
        self._set_headers()

    def do_GET(self):
        """ Handle a GET request """
        self._set_headers()
        self._send_body({'MESSAGE': ''})



class WebServer(object):
    """ Encapsulate all things related to webserver """

    def __init__(self, port, alarm_file):
        self.port = port
        self.timer = AlarmTimer(alarm_file)
        self.proc = None

    def handler(self, new_time):
        """ A handler called to set up a new time from server """
        self.timer.set_time(new_time)

    def templater(self, html, data={}):
        """ Insert data into the template """
        self.timer.load_file()

        data['CURRENT'] = self.timer.get_time().strftime("%H:%M")
        data['ENABLED'] = ''

        for key, value in data.items():
            html = html.replace('${}$'.format(key), str(value))

        return html

    def run(self):
        """ Start the server and set up its handlers """
        _log('starting server...')

        # Server settings
        server_address = ('', self.port)
        AlarmHTTPServer_RequestHandler.templater = self.templater
        AlarmHTTPServer_RequestHandler.handler = self.handler
        httpd = HTTPServer(server_address, AlarmHTTPServer_RequestHandler)
        _log('running server...')
        httpd.serve_forever()


class WebGUI(object):
    """ A wrapper around WebGUI module """
    def __init__(self, alarm_file):
        self.alarm_file = alarm_file
        self.proc = None

    def run(self):
        """ Start a http server in the background """
        self.proc = Process(target=self._new_proc)
        self.proc.start()

    def _new_proc(self):
        """ To be run in the other process """
        w = WebServer(8001, self.alarm_file)
        w.run()

    def __exit__(self, exc_type, exc_value, traceback):
        """ Clean """
        if self.proc:
            self.proc.join()
