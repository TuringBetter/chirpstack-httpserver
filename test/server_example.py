from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from chirpstack_api import integration
from google.protobuf.json_format import Parse

class Handler(BaseHTTPRequestHandler):
    json = False

    def do_POST(self):
        self.send_response(200)
        self.end_headers()
        query_args = parse_qs(urlparse(self.path).query)
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len)

        if query_args["event"][0] == "up":
            self.up(body)
        elif query_args["event"][0] == "join":
            self.join(body)
        else:
            print("Event not handled:", query_args["event"][0])

    def up(self, body):
        up = self.unmarshal(body, integration.UplinkEvent())
        print("Uplink from %s with payload: %s" % (up.device_info.dev_eui, up.data.hex()))

    def join(self, body):
        join = self.unmarshal(body, integration.JoinEvent())
        print("Join from %s with DevAddr: %s" % (join.device_info.dev_eui, join.dev_addr))

    def unmarshal(self, body, pl):
        if self.json:
            return Parse(body, pl)
        pl.ParseFromString(body)
        return pl

httpd = HTTPServer(('', 8090), Handler)  # '' 表示监听所有 IP
print("HTTP Server running at port 8090...")
httpd.serve_forever()
