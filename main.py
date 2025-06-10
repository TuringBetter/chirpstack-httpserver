from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
from chirpstack_api import integration
from chirpstack_api import api
from google.protobuf.json_format import Parse
import grpc
import base64
import requests
from datetime import datetime

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

# 状态同步服务器地址
STATUS_SERVER = "http://111.20.150.242:10088"

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
        15: 整体控制（颜色、频率、亮度、亮灯方式）
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

def sync_status(ip, status):
    """同步设备开关状态"""
    url = f"{STATUS_SERVER}/equipment/setStatus"
    params = {"ip": ip, "status": status}
    try:
        response = requests.get(url, params=params)
        return response.status_code == 200
    except Exception as e:
        print(f"同步开关状态失败: {str(e)}")
        return False

def sync_level(ip, level):
    """同步设备亮度级别"""
    url = f"{STATUS_SERVER}/equipment/setLevel"
    params = {"ip": ip, "level": level}
    try:
        response = requests.get(url, params=params)
        return response.status_code == 200
    except Exception as e:
        print(f"同步亮度级别失败: {str(e)}")
        return False

def sync_frequency(ip, frequency):
    """同步设备闪烁频率"""
    url = f"{STATUS_SERVER}/equipment/setFrequency"
    params = {"ip": ip, "frequency": frequency}
    try:
        response = requests.get(url, params=params)
        return response.status_code == 200
    except Exception as e:
        print(f"同步闪烁频率失败: {str(e)}")
        return False

def sync_color(ip, color):
    """同步设备亮灯颜色"""
    url = f"{STATUS_SERVER}/equipment/setColor"
    params = {"ip": ip, "color": color}
    try:
        response = requests.get(url, params=params)
        return response.status_code == 200
    except Exception as e:
        print(f"同步亮灯颜色失败: {str(e)}")
        return False

def sync_manner(ip, manner):
    """同步设备亮灯方式"""
    url = f"{STATUS_SERVER}/equipment/setManner"
    params = {"ip": ip, "manner": manner}
    try:
        response = requests.get(url, params=params)
        return response.status_code == 200
    except Exception as e:
        print(f"同步亮灯方式失败: {str(e)}")
        return False

def send_warn_info(stake_no, warn_type):
    """发送报警信息到状态服务器"""
    url = f"{STATUS_SERVER}/warn/warnInfo"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    params = {
        "stakeNo": stake_no,
        "eventDate": current_time,
        "warnType": warn_type
    }
    try:
        response = requests.get(url, params=params)
        return response.status_code == 200
    except Exception as e:
        print(f"发送报警信息失败: {str(e)}")
        return False

def send_heartbeat(stake_no):
    """发送心跳信息到状态服务器"""
    url = f"{STATUS_SERVER}/equipmentfailure/sendBeat"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "stakeNo": stake_no,
        "updateDate": current_time,
        "loraStatus": "Online"
    }
    try:
        response = requests.post(url, json=data)
        return response.status_code == 200
    except Exception as e:
        print(f"发送心跳信息失败: {str(e)}")
        return False

# HTTP 事件处理服务
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # 获取请求体
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        event = parsed_path.query.split("=")[-1]

        # 由终端发来的上行数据
        if event == "up":
            body_json = json.loads(body)
            dev_eui = body_json.get("deviceInfo", {}).get("devEui", "")
            data_hex = body_json.get("data", "")

            try:
                decoded_data = base64.b64decode(data_hex)

                if len(decoded_data) > 0:
                    cmd_code = decoded_data[0]
                    
                    # 处理延迟测量请求 (命令码 0x06)
                    if cmd_code == 0x06:
                        # 立即发送响应，使用相同的命令码
                        data = bytes([0x06])
                        downlink_id = send_downlink(dev_eui, 1, data)
                        print(f"已发送延迟测量响应，下行ID：{downlink_id}")
                        return
                    # 处理人工报警 (命令码 0x07)
                    elif cmd_code == 0x07:
                        print(f"收到来自设备 {dev_eui} 的人工报警")
                        if send_warn_info(dev_eui, 1):
                            print(f"已成功转发人工报警信息到状态服务器")
                        return
                    # 处理事故报警 (命令码 0x08)
                    elif cmd_code == 0x08:
                        print(f"收到来自设备 {dev_eui} 的事故报警")
                        if send_warn_info(dev_eui, 2):
                            print(f"已成功转发事故报警信息到状态服务器")
                        return
                    elif cmd_code == 0x09:
                        print(f"收到来自设备 {dev_eui} 的心跳数据")
                        if send_heartbeat(dev_eui):
                            print(f"已成功转发心跳信息到状态服务器")
                        return
                return
            except Exception as e:
                print(f"数据处理错误：{str(e)}")
                return

        # 由外部系统发来的请求
        try:
            commands = json.loads(body)
            if not isinstance(commands, list):
                self._send_response(400, "请求体必须是数组格式")
                return
                
            # 根据不同的路径处理不同的请求
            if path == '/api/induction-lights/set-color':
                self._handle_set_color(commands)
            elif path == '/api/induction-lights/set-frequency':
                self._handle_set_frequency(commands)
            elif path == '/api/induction-lights/set-level':
                self._handle_set_level(commands)
            elif path == '/api/induction-lights/set-manner':
                self._handle_set_manner(commands)
            elif path == '/api/induction-lights/set-switch':
                self._handle_set_switch(commands)
            elif path == '/api/induction-lights/overall-setting':
                self._handle_overall_setting(commands)
            elif path == '/api/induction-flashing-lights/set-switch':
                self._handle_flashing_lights(commands)
            else:
                self._send_response(404, "不支持的请求路径")
                
        except json.JSONDecodeError:
            self._send_response(400, "无效的JSON格式")
        except Exception as e:
            self._send_response(500, f"服务器内部错误: {str(e)}")
            
    def _handle_set_color(self, commands):
        """处理设置颜色请求"""
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'color']):
                self._send_response(400, "缺少必要参数")
                return
                
            if cmd['color'] not in [0, 1]:
                self._send_response(400, "颜色值必须是0或1")
                return
                
            dev_euis = cmd['stakeNo'].split(',')
            for dev_eui in dev_euis:
                data = bytes([cmd['color']])
                send_downlink(dev_eui, 11, data)
                
        self._send_response(200, "Color setting applied successfully.")
        
    def _handle_set_frequency(self, commands):
        """处理设置频率请求"""
        freq_map = {30: 0x1E, 60: 0x3C, 120: 0x78}
        
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'frequency']):
                self._send_response(400, "缺少必要参数")
                return
                
            if cmd['frequency'] not in freq_map:
                self._send_response(400, "频率值必须是30、60或120")
                return
                
            dev_euis = cmd['stakeNo'].split(',')
            for dev_eui in dev_euis:
                data = bytes([freq_map[cmd['frequency']]])
                send_downlink(dev_eui, 10, data)
                
        self._send_response(200, "Frequency setting applied successfully.")
        
    def _handle_set_level(self, commands):
        """处理设置亮度请求"""
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'level']):
                self._send_response(400, "缺少必要参数")
                return
                
            if cmd['level'] not in [500, 1000, 2000, 4000, 7000]:
                self._send_response(400, "亮度值必须是500、1000、2000、4000或7000")
                return
                
            dev_euis = cmd['stakeNo'].split(',')
            for dev_eui in dev_euis:
                high_byte = (cmd['level'] >> 8) & 0xFF
                low_byte = cmd['level'] & 0xFF
                data = bytes([high_byte, low_byte])
                send_downlink(dev_eui, 13, data)
                
        self._send_response(200, "Level setting applied successfully.")
        
    def _handle_set_manner(self, commands):
        """处理设置亮灯方式请求"""
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'manner']):
                self._send_response(400, "缺少必要参数")
                return
                
            if cmd['manner'] not in [0, 1]:
                self._send_response(400, "亮灯方式必须是0或1")
                return
                
            dev_euis = cmd['stakeNo'].split(',')
            for dev_eui in dev_euis:
                data = bytes([cmd['manner']])
                send_downlink(dev_eui, 12, data)
                
        self._send_response(200, "Manner setting applied successfully.")
        
    def _handle_set_switch(self, commands):
        """处理设置开关请求"""
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'switch']):
                self._send_response(400, "缺少必要参数")
                return
                
            if cmd['switch'] not in [0, 1]:
                self._send_response(400, "开关状态必须是0或1")
                return
                
            dev_euis = cmd['stakeNo'].split(',')
            for dev_eui in dev_euis:
                data = bytes([cmd['switch']])
                send_downlink(dev_eui, 14, data)
                
        self._send_response(200, "Switch setting applied successfully.")
        
    def _handle_overall_setting(self, commands):
        """处理整体设置请求"""
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'color', 'frequency', 'level', 'manner']):
                self._send_response(400, "缺少必要参数")
                return
                
            # 验证颜色参数
            if cmd['color'] not in [0, 1]:
                self._send_response(400, "颜色值必须是0或1")
                return
                
            # 验证频率参数
            if cmd['frequency'] not in [30, 60, 120]:
                self._send_response(400, "频率值必须是30、60或120")
                return
                
            # 验证亮度参数
            if cmd['level'] not in [500, 1000, 2000, 4000, 7000]:
                self._send_response(400, "亮度值必须是500、1000、2000、4000或7000")
                return
                
            # 验证亮灯方式参数
            if cmd['manner'] not in [0, 1]:
                self._send_response(400, "亮灯方式必须是0或1")
                return
                
            # 构建payload
            # 第一个字节：颜色
            color_byte = bytes([cmd['color']])
            # 第二个字节：频率
            freq_map = {30: 0x1E, 60: 0x3C, 120: 0x78}
            freq_byte = bytes([freq_map[cmd['frequency']]])
            # 第三、四字节：亮度
            high_byte = (cmd['level'] >> 8) & 0xFF
            low_byte = cmd['level'] & 0xFF
            level_bytes = bytes([high_byte, low_byte])
            # 第五个字节：亮灯方式
            manner_byte = bytes([cmd['manner']])
            
            # 组合所有字节
            payload = color_byte + freq_byte + level_bytes + manner_byte
            
            # 处理多个设备编号
            dev_euis = cmd['stakeNo'].split(',')
            for dev_eui in dev_euis:
                send_downlink(dev_eui, 15, payload)
                
        self._send_response(200, "Overall setting applied successfully.")

    def _handle_flashing_lights(self,commands):
        """处理设置爆闪灯请求"""
        print("flashing_lights...")
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'switch']):
                self._send_response(400, "缺少必要参数")
                return
                
            if cmd['switch'] not in [0, 1]:
                self._send_response(400, "开关状态必须是0或1")
                return
            
            fPort = 17 if cmd['switch'] == 0 else 16
            data=bytes([cmd['switch']])
            dev_euis = cmd['stakeNo'].split(',')
            for dev_eui in dev_euis:
                send_downlink(dev_eui, fPort,data)
                
        self._send_response(200, "Switch setting applied successfully.")

    def _send_response(self, code, message):
        """发送JSON格式的响应"""
        response = {
            "code": code,
            "message": message
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