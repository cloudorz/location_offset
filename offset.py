# coding: utf-8

import httplib, math, decimal, sys

import tornado.web
import tornado.httpclient
import tornado.database
from tornado.escape import json_encode, json_decode
from tornado.web import HTTPError

CREATE_SYNTAX = '''
CREATE TABLE IF NOT EXISTS %s (
	id INT(10) UNSIGNED NOT NULL AUTO_INCREMENT,
    address CHAR(200) NOT NULL,
	ne_lat DOUBLE NOT NULL,
	ne_lon DOUBLE NOT NULL,
	sw_lat DOUBLE NOT NULL,
	sw_lon DOUBLE NOT NULL,
	PRIMARY KEY (id)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8
'''

INSERT_SYNTAX = '''
INSERT INTO %s SET ne_lat=%s, ne_lon=%s, sw_lat=%s, sw_lon=%s, address='%s'
'''

class BasicRequestHandler(tornado.web.RequestHandler):

    @property
    def db(self):
        return self.application.db_connect

    def get_error_html(self, status_code, **kwargs):
        ''' all error response where json data {'code': ..., 'msg': ...}
        '''
        return self.render_json({'code': status_code, 'msg': httplib.responses[status_code]})

    def render_json(self, data, **kwargs):
        self.set_header('Content-Type', 'Application/json; charset=UTF-8')
        self.write(json_encode(data))


class OffsetHandler(BasicRequestHandler):

    def get(self, lat, lon):

        lat, lon = float(lat), float(lon)
        t_name = "offset_%s_%s" % (int(lat/3 + 0.5), int(lon/3 + 0.5))

        try:
            entries = self.db.query("SELECT * FROM " + t_name + " WHERE lat=%s AND lon=%s", int(lat*100+0.5), int(lon*100+0.5))
        except Exception:
            entries = []

        fake_lat, fake_lon = lat, lon
        if entries:
            op = OffsetPos(lat, lon, entries[0])
            fake_lat, fake_lon = op.getFakePos()

        fake_lat = float(decimal.Decimal(fake_lat).quantize(decimal.Decimal('0.000001')))
        fake_lon = float(decimal.Decimal(fake_lon).quantize(decimal.Decimal('0.000001')))

        self.render_json({'lat': fake_lat, 'lon': fake_lon})


class AddressHandler(BasicRequestHandler):

    def get(self, lat, lon):

        lat, lon = float(lat), float(lon)
        t_name = "offset_%s_%s" % (int(lat/3 + 0.5), int(lon/3 + 0.5))

        try:
            entries = self.db.query("SELECT address FROM " + t_name + "WHERE %(lat)f > sw_lat AND \
                    %(lat)f < ne_lat AND %(lon)f > sw_lon AND %(lon)f < ne_lat"
                    % {'lat': lat, 'lon': lon })
        except Exception:
            entries = []

        if entries:
            addr = entries[0].address
        else:
            addr = self.add_new_address(t_name, lat, lon)

        self.render_json(addr)

    def add_new_address(self, t_name, lat, lon):

        http = tornado.httpclient.HTTPClient()
        try:
            print >> sys.stderr, 'fuck'
            res = http.fetch("http://maps.google.com/maps/api/geocode/json?latlng=%f,%f&sensor=true" % (lat, lon))
            print >> sys.stderr, 'fuck2'
        except tornado.httpclient.HTTPError:
            res = None

        addr = None
        if res and res.body:
            addr_info = json_decode(res.body)
            if add_info['status'] == 'OK':
                print >> sys.stderr, 'fuck3'
                ne, sw, addr = self.extract_addr_info(addr_info)

                self.save_info2db(t_name, [ne['lat'], ne['lng'], sw['lat'], sw['lng'], addr])

        return addr

    def extract_addr_info(self, info):

        street_addr_dict = None
        for e in info['results']:
            if 'street_address' in e['types']:
                street_addr_dict = e
                break

        if not street_addr_list:
            return None

        street_addr_list = []
        political_addr_list = []
        for e in street_addr_dict['address_components']:
            if 'political' in e['types']:
                political_addr_list.insert(0, e['long_name'])
            else:
                street_addr_dict.insert(0, e['long_name'])
        street_addr = "%s#%s" % (','.join(political_addr_list), ','.join(street_addr_dict))

        bound = street_add_dict['geometry']['bounds']

        return bound['northeast'], bound['southwest'], street_addr

    def save_info2db(self, t_name, info):
        info.insert(0, t_name)
        self.db.execute(CREATE_SYNTAX % t_name)
        self.db.execute(INSERT_SYNTAX % tuple(info))


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
