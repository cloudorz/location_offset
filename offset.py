# coding: utf-8

import httplib

import tornado.web
import tornado.database
from tornado.escape import json_encode
from tornado.web import HTTPError


class OffsetHandler(tornado.web.RequestHandler):

    def get(self, lat, lon):
        try:
            entry = self.db.get("SELECT * FROM cn_map_offset WHERE lat=%s AND lon=%s", int(float(lat)*100), int(float(lon)*100))
        except Exception:
            raise HTTPError(500)

        if not entry:
            raise HTTPError(404)

        self.render_json({'off_x': entry.off_x, 'off_y': entry.off_y})

    @property
    def db(self):
        return tornado.database.Connection(
            host="127.0.0.1:3306", database="gis",
            user="root", password="123")

    def get_error_html(self, status_code, **kwargs):
        ''' all error response where json data {'code': ..., 'msg': ...}
        '''
        return self.render_json({'code': status_code, 'msg': httplib.responses[status_code]})

    def render_json(self, data, **kwargs):
        self.set_header('Content-Type', 'Application/json; charset=UTF-8')
        self.write(json_encode(data))
