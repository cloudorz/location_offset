# coding: utf-8

import httplib, math, decimal, hashlib, sys

import tornado.web
import tornado.httpclient
import tornado.database
from tornado.escape import json_encode, json_decode
from tornado.web import HTTPError


class BasicRequestHandler(tornado.web.RequestHandler):

    @property
    def db(self):
        return self.application.db_connect

    @property
    def rdb(self):
        return self.application.redis

    def get_error_html(self, status_code, **kwargs):
        ''' all error response where json data {'code': ..., 'msg': ...}
        '''
        return self.render_json({'code': status_code, 'msg': httplib.responses[status_code]})

    def render_json(self, data, **kwargs):
        self.set_header('Content-Type', 'Application/json; charset=UTF-8')
        self.write(data)


class OffsetHandler(BasicRequestHandler):

    def get(self, lat, lon):

        lat, lon = float(lat), float(lon)
        lat_100, lon_100 =  int(lat*100+0.5), int(lon*100+0.5)
        key = "e2m:%s" % hashlib.md5("%s%s" % (lat_100, lon_100)).hexdigest()

        off_json = self.rdb.get(key)
        if not off_json:
            t_name = "offset_%s_%s" % (int(lat/3 + 0.5), int(lon/3 + 0.5))
            try:
                entries = self.db.query("SELECT off_x, off_y FROM " + t_name + " WHERE lat=%s AND lon=%s", lat_100, lon_100)
            except Exception:
                entries = None

            if entries:
                off_dict = entries[0]
                self.rdb.set(key, json_encode(off_dict))
            else:
                off_dict = None
        else:
            off_dict = json_decode(off_json)

        fake_lat, fake_lon = lat, lon
        if off_dict:
            op = OffsetPos(lat, lon, off_dict)
            fake_lat, fake_lon = op.getFakePos()

        fake_lat = float(decimal.Decimal(fake_lat).quantize(decimal.Decimal('0.000001')))
        fake_lon = float(decimal.Decimal(fake_lon).quantize(decimal.Decimal('0.000001')))
        res = json_encode({'lat': fake_lat, 'lon': fake_lon})

        self.render_json(res)


class AddressHandler(BasicRequestHandler):

    def get(self, lat, lon):

        lat, lon = float(lat), float(lon)
        key = self.pixel2key(lat, lon)

        res = self.rdb.get(key)

        if not res:
            addr = self.retrive_addr(lat, lon)
            res = addr
            # get the addr save it to redis db
            if addr:
                self.rdb.set(key, res)

        self.render_json(res)

    def pixel2key(self, lat, lon):

        lat_10000, lon_10000 = self.int05(lat), self.int05(lon)
        return "m2addr:%s" % hashlib.md5("%s%s" % (lat_10000, lon_10000)).hexdigest()

    def int05(self, f):

        partial = f*10000 - int(f*1000)*10
        if partial < 2.5:
            plus = 0
        elif partial >= 2.5 and partial < 7.5:
            plus = 5
        elif partial >= 7.5 and partial < 10:
            plus = 10
        else:
            plus = 0

        return int(f*1000)*10 + plus

    def retrive_addr(self, lat, lon):

        http = tornado.httpclient.HTTPClient()
        try:
            res = http.fetch(
                    "http://maps.google.com/maps/api/geocode/json?latlng=%f,%f&sensor=true&language=zh-CN"
                    % (lat, lon))
        except tornado.httpclient.HTTPError:
            res = None

        addr = None
        if res and res.body:
            addr_info = json_decode(res.body)
            if addr_info['status'] == 'OK':
                addr = self.extract_addr_info(addr_info)

        return addr

    def extract_addr_info(self, info):

        street_addr_dict = None
        for e in info['results']:
            if 'street_address' in e['types']:
                street_addr_dict = e
                break

        if not street_addr_dict:
            return None

        street_addr_list = []
        political_addr_list = []
        for e in street_addr_dict['address_components']:
            if 'political' in e['types']:
                political_addr_list.insert(0, e['long_name'])
            else:
                street_addr_list.insert(0, e['long_name'])
        street_addr = "%s#%s" % (','.join(political_addr_list), ','.join(street_addr_list))

        return street_addr


class OffsetPos(object):

    def __init__(self, lat, lon, entry, zoom=18):
        self.lat, self.lon = lat, lon 
        self.off_x, self.off_y = entry['off_x'], entry['off_y']
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
