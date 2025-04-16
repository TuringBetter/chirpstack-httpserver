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

# 从JSON文件加载IP和DEV_EUI的对应关系
def load_ip_devices():
    with open('ip_devices.json', 'r') as f:
        return json.load(f)

# 设置 ChirpStack gRPC 接口地址 和 API Token
CHIRPSTACK_SERVER = "49.232.192.237:18080"
API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6IjQyOTVmNTUxLTU5YzEtNGIwOS1iMmRhLTBkNjFmYTQ2YmI1NiIsInR5cCI6ImtleSJ9.cgiNxrWfEuPjgwHOQs6t_wrXzH0q7vC_NoN42Y68r4Q"

# 加载所有交通灯的DEV_EUI
TRAFFIC_LIGHTS = load_dev_euis()['traffic_lights']
# 加载IP和DEV_EUI的对应关系
IP_DEVICES = load_ip_devices()

# 创建 gRPC 通道和客户端
channel = grpc.insecure_channel(CHIRPSTACK_SERVER)
client = api.DeviceServiceStub(channel)
auth_token = [("authorization", f"Bearer {API_TOKEN}")]

# 下行发送函数
def send_downlink(dev_eui, f_port, data_bytes=None):
    """
    发送下行控制命令
    :param dev_eui: 设备EUI
    :param f_port: 端口号,根据协议规范：
        10: 设置闪烁频率
        11: 设置LED颜色
        12: 设置是否闪烁
        13: 设置亮度
        14: 设备开关控制
        20: 车辆通过状态（红色+7000亮度+120Hz)
        21: 车辆离开状态（黄色+1000亮度+常亮）
    :param data_bytes: 数据载荷,对于f_port=20/21可以为None
    """
    req = api.EnqueueDeviceQueueItemRequest()
    req.queue_item.dev_eui = dev_eui
    req.queue_item.f_port = f_port
    req.queue_item.confirmed = False
    
    if data_bytes is not None:
        req.queue_item.data = data_bytes
    
    resp = client.Enqueue(req, metadata=auth_token)
    print(f"下行已发送给 {dev_eui}, fPort={f_port}, downlink ID: {resp.id}")
    return resp.id

# HTTP 事件处理服务
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        params = parse_qs(parsed_path.query)
        
        # 获取设备EUI或IP
        dev_eui = params.get('DevEUI', [''])[0]
        ip = params.get('ip', [''])[0]
        
        # 如果没有提供DevEUI或IP参数
        if not dev_eui and not ip:
            self._send_response(400, "缺少设备DevEUI或IP参数")
            return
            
        # 获取目标设备列表
        target_devices = []
        if dev_eui:
            target_devices = [dev_eui]
        elif ip:
            if ip in IP_DEVICES:
                target_devices = IP_DEVICES[ip]
            else:
                self._send_response(400, f"未找到IP {ip} 对应的设备")
                return
            
        # 根据不同的路径处理不同的请求
        if path == '/equipment/setLevel':
            level = params.get('level', [''])[0]
            if not level:
                self._send_response(400, "缺少亮度参数")
                return
            try:
                level = int(level)
                # 将亮度值转换为大端序的2字节
                high_byte = (level >> 8) & 0xFF
                low_byte = level & 0xFF
                data = bytes([high_byte, low_byte])
                downlink_ids = []
                for dev in target_devices:
                    downlink_id = send_downlink(dev, 13, data)
                    downlink_ids.append(downlink_id)
                self._send_response(200, f"设置亮度成功，亮度值：{level}，下行ID：{downlink_ids}")
            except ValueError:
                self._send_response(400, "亮度参数必须是数字")
                
        elif path == '/equipment/setFrequency':
            frequency = params.get('frequency', [''])[0]
            if not frequency:
                self._send_response(400, "缺少频率参数")
                return
            try:
                frequency = int(frequency)
                if frequency not in [30, 60, 120]:
                    self._send_response(400, "频率必须是30、60或120")
                    return
                # 将频率转换为对应的十六进制值
                freq_map = {30: 0x1E, 60: 0x3C, 120: 0x78}
                data = bytes([freq_map[frequency]])
                downlink_ids = []
                for dev in target_devices:
                    downlink_id = send_downlink(dev, 10, data)
                    downlink_ids.append(downlink_id)
                self._send_response(200, f"设置频率成功，频率值：{frequency}Hz，下行ID：{downlink_ids}")
            except ValueError:
                self._send_response(400, "频率参数必须是数字")
                
        elif path == '/equipment/setColor':
            color = params.get('color', [''])[0]
            if not color:
                self._send_response(400, "缺少颜色参数")
                return
            try:
                color = int(color)
                if color not in [0, 1]:
                    self._send_response(400, "颜色参数必须是0(红色)或1(黄色)")
                    return
                data = bytes([color])
                downlink_ids = []
                for dev in target_devices:
                    downlink_id = send_downlink(dev, 11, data)
                    downlink_ids.append(downlink_id)
                color_name = "红色" if color == 0 else "黄色"
                self._send_response(200, f"设置颜色成功，颜色：{color_name}，下行ID：{downlink_ids}")
            except ValueError:
                self._send_response(400, "颜色参数必须是数字")
                
        elif path == '/equipment/setManner':
            manner = params.get('manner', [''])[0]
            if not manner:
                self._send_response(400, "缺少闪烁方式参数")
                return
            try:
                manner = int(manner)
                if manner not in [0, 1]:
                    self._send_response(400, "闪烁方式参数必须是0(闪烁)或1(常亮)")
                    return
                data = bytes([manner])
                downlink_ids = []
                for dev in target_devices:
                    downlink_id = send_downlink(dev, 12, data)
                    downlink_ids.append(downlink_id)
                manner_name = "闪烁" if manner == 0 else "常亮"
                self._send_response(200, f"设置闪烁方式成功，方式：{manner_name}，下行ID：{downlink_ids}")
            except ValueError:
                self._send_response(400, "闪烁方式参数必须是数字")
                
        elif path == '/equipment/setStatus':
            status = params.get('status', [''])[0]
            if not status:
                self._send_response(400, "缺少状态参数")
                return
            try:
                status = int(status)
                if status not in [0, 1]:
                    self._send_response(400, "状态参数必须是0(关闭)或1(开启)")
                    return
                    
                # 根据状态发送开关命令
                data = bytes([0x01 if status == 1 else 0x00])
                downlink_ids = []
                for dev in target_devices:
                    downlink_id = send_downlink(dev, 14, data)
                    downlink_ids.append(downlink_id)
                status_name = "开启" if status == 1 else "关闭"
                self._send_response(200, f"{status_name}成功，下行ID：{downlink_ids}")
            except ValueError:
                self._send_response(400, "状态参数必须是数字")
                
        else:
            self._send_response(404, "不支持的请求路径")
            
    def do_POST(self):
        parsed_path = urlparse(self.path)
        event = parsed_path.query.split("=")[-1]

        length = int(self.headers.get("Content-Length"))
        body = self.rfile.read(length)
        body_json = json.loads(body)

        if event == "up":
            dev_eui = body_json.get("deviceInfo", {}).get("devEui", "")
            data_hex = body_json.get("data", "")
            
            # 解析上行数据
            try:
                data_bytes = bytes.fromhex(data_hex)
                if len(data_bytes) > 0:
                    cmd_code = data_bytes[0]
                    # 处理延迟测量请求 (命令码 0x06)
                    if cmd_code == 0x06:
                        # 立即发送响应，使用相同的命令码
                        data = bytes([0x06])
                        downlink_id = send_downlink(dev_eui, 1, data)
                        print(f"已发送延迟测量响应，下行ID：{downlink_id}")
                        return
            except ValueError:
                print("无法解析上行数据")
            
            # 解析设备位置
            direction = "顺行" if dev_eui[0] == "1" else "逆行"
            position = "左侧" if dev_eui[1] == "1" else "右侧"
            number = int(dev_eui[-4:])  # 取最后4位作为序号
            print(f"收到{direction}{position}第{number}号灯的上行数据")
            
            # 示例：当收到上行数据时，设置该灯为"车辆通过"状态
            # send_downlink(dev_eui, 20)  # 使用fPort=20表示车辆通过状态

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
        
    def _send_response(self, code, msg):
        """发送JSON格式的响应"""
        response = {
            "msg": msg,
            "code": code
        }
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

# 启动 HTTP 服务
if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 10088), Handler)
    print("HTTP Server running at port 10088...")
    server.serve_forever()