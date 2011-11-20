# coding: utf-8

import tornado.ioloop
import tornado.web
import tornado.options
import tornado.httpserver

from tornado.options import define, options
from offset import OffsetHandler

# server
define('port', default=8888, help="run on the given port", type=int)

app = tornado.web.Application([
    (r"^/(\d+\.\d+),(\d+\.\d+)$", OffsetHandler),
    ])

app.db_connect = tornado.database.Connection(
            host="127.0.0.1:3306", database="gis",
            user="root", password="123")

def main():
    tornado.options.parse_command_line()

    http_server = tornado.httpserver.HTTPServer(app, xheaders=True)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()
