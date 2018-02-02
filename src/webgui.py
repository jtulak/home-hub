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
import re
import datetime as dt
import urllib.parse
from multiprocessing import Process
from src.alarm import AlarmTimer
from huefri.common import log

__all__ = ["WebGUI"]

def _log(msg):
    log("WebGUI", msg)

THISDIR = os.path.dirname(os.path.realpath(__file__))

def addtime(time, delta):
    return (dt.datetime.combine(dt.date(1,1,1),time) + delta).time()

# HTTPRequestHandler class
class AlarmHTTPServer_RequestHandler(BaseHTTPRequestHandler):
    """ HTTP request handler modified for alarm """

    templater = None
    handler = None
    template_path = os.path.join(THISDIR, 'webgui.html')

    def _send_headers(self, code, content_type):
        self.send_response(code)
        self.send_header('Content-type', content_type)
        self.end_headers()


    def _send_html(self, data={}):
        """ Send html """
        # Send message back to client
        with open(self.template_path, 'r') as f:
            message = f.read()

        if self.templater:
            message = self.templater(message, data=data)

        # Write content as utf-8 data
        self.wfile.write(bytes(message, "utf8"))

    def _redirect(self, target, message=None):
        self.send_response(301)
        if message:
            target +='?message={}'.format(urllib.parse.quote(message))
        self.send_header('Location', target)
        self.end_headers()

    def _send_image(self, filename):
        self._send_headers(200, 'image/x-icon')
        # Send message back to client
        with open(filename, 'rb') as file:
            self.wfile.write(file.read())

    def get_POST_data(self):
        """ Return a dict with POST data, empty dict if no data present """
        try:
            return self._data_post
        except AttributeError:
            content_length = int(self.headers['Content-Length'])

            data = {}
            for line in self.rfile.read(content_length).decode("utf-8").split('&'):
                key, val = urllib.parse.unquote(line).split('=')
                data[key] = val
            _log('Got POST data: {}'.format(data))
            self._data_post = data
            return self._data_post

    def get_GET_data(self):
        """ Return a dict {key1:val, key2:val, ...} for GET query """
        try:
            return self._data_get
        except AttributeError:
            url = urllib.parse.urlparse(self.path)
            if url.query:
                self._data_get = dict(
                    (map(urllib.parse.unquote, val.split('=')))
                    for val in url.query.split('&')
               )
            else:
                self._data_get = dict()
            return self._data_get

    def do_POST(self):
        """ Handle a POST request """
        data = self.get_POST_data()
        new_time = dt.datetime.strptime(data['time'], '%H:%M').time()
        enabled = data['enabled'] if 'enabled' in data else False
        self.handler(new_time=new_time, enabled=enabled)

        self._redirect(urllib.parse.urlparse(self.path).path)

    def do_GET(self):
        """ Handle a GET request """
        url = urllib.parse.urlparse(self.path)
        if url.path == '/favicon.ico':
            self._send_image(os.path.join(THISDIR, 'favicon.ico'))
        elif url.path == '/apple-touch-icon.png':
            self._send_image(os.path.join(THISDIR, 'apple-touch-icon.png'))
        elif url.path == '/':
            self._send_headers(200, 'text/html')
            get_data = self.get_GET_data()
            self._send_html({'MESSAGE': get_data.get('message', '')})
        else:
            self._send_headers(404, 'text/html')
            self._send_html({'MESSAGE': 'Error 404, this url does not exist. There is only one site.'})



class WebServer(object):
    """ Encapsulate all things related to webserver """

    def __init__(self, port, alarm_file):
        self.port = port
        self.timer = AlarmTimer(alarm_file)
        self.proc = None

    def handler(self, new_time, enabled):
        """ A handler called to set up a new time from server """
        new_time = addtime(new_time, -dt.timedelta(seconds=60*20))
        self.timer.set_time(new_time, enabled)

    def templater(self, html, data={}):
        """ Insert data into the template """
        self.timer.load_file()
        time = addtime(self.timer.get_time(), dt.timedelta(seconds=60*20))

        data['CURRENT'] = time.strftime("%H:%M")
        data['ENABLED'] = 'checked' if self.timer.enabled else ''

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
