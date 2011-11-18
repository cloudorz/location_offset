# coding: utf-8

import httplib, math

import tornado.web
import tornado.database
from tornado.escape import json_encode
from tornado.web import HTTPError


class OffsetHandler(tornado.web.RequestHandler):

    def get(self, lat, lon):

        lat, lon = float(lat), float(lon)
        entries = self.db.query("SELECT * FROM cn_map_offset WHERE lat=%s AND lon=%s", int(lat*100), int(lon*100))

        fake_lat, fake_lon = lat, lon
        if entries:
            op = OffsetPos(lat, lon, entries[0])
            fake_lat, fake_lon = op.getFakePos()

        self.render_json({'lat': fake_lat, 'lon': fake_lon})

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

class OffsetPos(object):

    def __init__(self, lat, lon, entry, zoom=18):
        self.lat, self.lon = lat, lon 
        self.off_x, self.off_y = entry.off_x, entry.off_y
        self.zoom = zoom

    def getFakePos(self):
        lat_pixel, lon_pixel = self.lat2pixel(), self.lon2pixel()

        lat_pixel += self.off_y
        lon_pixel += self.off_x

        return self.pixel2lat(lat_pixel), self.pixel2lon(lon_pixel)

    def lat2pixel(self):
        siny = math.sin(self.lat*math.pi / 180)
        y = math.log((1 + siny) / (1 - siny))

        return (128 << self.zoom) * (1 - y / (2*math.pi))

    def lon2pixel(self):
        return (self.lon + 180) * (256 << self.zoom) / 360
    
    def pixel2lat(self, pixelY):
        y = 2 * math.pi * (1 - pixelY / (128 << self.zoom))
        z = math.pow(math.e, y)
        siny = (z - 1) / (z + 1)

        return math.asin(siny) * 180 /math.pi

    def pixel2lon(self, pixelX):
        return pixelX * 360 / (256 << self.zoom) - 180
