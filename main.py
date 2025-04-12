from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json

from chirpstack_api import integration
from chirpstack_api import api

from google.protobuf.json_format import Parse
import grpc

# 从JSON文件加载DEV_EUI
def load_dev_euis():
    with open('DEV_EUI.json', 'r') as f:
        return json.load(f)

# 设置 ChirpStack gRPC 接口地址 和 API Token
CHIRPSTACK_SERVER = "49.232.192.237:18080"
API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6IjQyOTVmNTUxLTU5YzEtNGIwOS1iMmRhLTBkNjFmYTQ2YmI1NiIsInR5cCI6ImtleSJ9.cgiNxrWfEuPjgwHOQs6t_wrXzH0q7vC_NoN42Y68r4Q"

# 加载所有交通灯的DEV_EUI
TRAFFIC_LIGHTS = load_dev_euis()['traffic_lights']

# 创建 gRPC 通道和客户端
channel = grpc.insecure_channel(CHIRPSTACK_SERVER)
client = api.DeviceServiceStub(channel)
auth_token = [("authorization", f"Bearer {API_TOKEN}")]

# 下行发送函数
def send_downlink(dev_eui, data_bytes):
    req = api.EnqueueDeviceQueueItemRequest()
    req.queue_item.dev_eui = dev_eui
    req.queue_item.data = data_bytes
    req.queue_item.confirmed = False
    req.queue_item.f_port = 10
    resp = client.Enqueue(req, metadata=auth_token)
    print(f"下行已发送给 {dev_eui}, downlink ID: {resp.id}")

# HTTP 事件处理服务
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        parsed_path = urlparse(self.path)
        event = parsed_path.query.split("=")[-1]

        length = int(self.headers.get("Content-Length"))
        body = self.rfile.read(length)
        body_json = json.loads(body)

        if event == "up":
            dev_eui = body_json.get("deviceInfo", {}).get("devEui", "")
            data_hex = body_json.get("data", "")
            print(f"收到上行：设备 {dev_eui}, 数据: {data_hex}")
            
            # 解析设备位置
            direction = "顺行" if dev_eui[0] == "1" else "逆行"
            position = "左侧" if dev_eui[1] == "1" else "右侧"
            number = int(dev_eui[-4:])  # 取最后4位作为序号
            print(f"收到{direction}{position}第{number}号灯的上行数据")
            # 这里可以添加交通灯控制逻辑

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

# 启动 HTTP 服务
if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 10088), Handler)
    print("HTTP Server running at port 10088...")
    server.serve_forever()