# handlers.py
import json
import base64
from config import Config

class UplinkHandler:
    """处理来自设备的上行数据"""
    def __init__(self, chirpstack_client, status_server_client):
        self.chirpstack_client = chirpstack_client
        self.status_server_client = status_server_client

    def process(self, body):
        try:
            body_json = json.loads(body)
            dev_eui = body_json.get("deviceInfo", {}).get("devEui", "")
            data_b64 = body_json.get("data", "")
            if not dev_eui or not data_b64:
                return
                
            decoded_data = base64.b64decode(data_b64)
            if not decoded_data:
                return

            cmd_code = decoded_data[0]
            
            handlers = {
                0x06: self.handle_latency_measure,
                0x07: self.handle_manual_alarm,
                0x08: self.handle_accident_alarm,
                0x09: self.handle_heartbeat,
            }
            
            handler = handlers.get(cmd_code)
            if handler:
                handler(dev_eui, decoded_data)
            else:
                print(f"收到未知命令码 {hex(cmd_code)} from {dev_eui}")

        except (json.JSONDecodeError, KeyError, IndexError, base64.binascii.Error) as e:
            print(f"处理上行数据时出错: {e}")

    def handle_latency_measure(self, dev_eui, _):
        print(f"收到来自 {dev_eui} 的延迟测量请求，正在响应...")
        self.chirpstack_client.send_downlink(dev_eui, 1, bytes([0x06]))

    def handle_manual_alarm(self, dev_eui, _):
        print(f"收到来自 {dev_eui} 的人工报警")
        self.status_server_client.send_warn_info(dev_eui, 1)

    def handle_accident_alarm(self, dev_eui, _):
        print(f"收到来自 {dev_eui} 的事故报警")
        self.status_server_client.send_warn_info(dev_eui, 2)

    def handle_heartbeat(self, dev_eui, _):
        print(f"收到来自 {dev_eui} 的心跳")
        self.status_server_client.send_heartbeat(dev_eui)

class APIHandler:
    """处理来自外部系统的API请求"""
    def __init__(self, chirpstack_client):
        self.chirpstack_client = chirpstack_client

    def _api_handler_decorator(func):
        """处理API请求通用逻辑的装饰器"""
        def wrapper(self, handler_instance, body):
            try:
                commands = json.loads(body)
                if not isinstance(commands, list):
                    handler_instance._send_response(400, "请求体必须是JSON数组格式")
                    return
                
                error_msg = func(self, commands)
                if error_msg:
                    handler_instance._send_response(400, error_msg)
                else:
                    handler_instance._send_response(200, "指令已成功应用")
            
            except json.JSONDecodeError:
                handler_instance._send_response(400, "无效的JSON格式")
            except Exception as e:
                print(f"API处理时发生内部错误: {e}")
                handler_instance._send_response(500, f"服务器内部错误: {str(e)}")
        return wrapper

    # --- 以下所有 API 处理方法都使用装饰器简化 ---
    
    @_api_handler_decorator
    def set_color(self, commands):
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'color']) or cmd['color'] not in [0, 1]:
                return "参数错误: 必须包含 'stakeNo' 和 'color' (0或1)"
            data = bytes([cmd['color']])
            for dev_eui in cmd['stakeNo'].split(','):
                self.chirpstack_client.send_downlink(dev_eui, 11, data)
        return None # 表示成功

    @_api_handler_decorator
    def set_frequency(self, commands):
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'frequency']) or cmd['frequency'] not in Config.FREQ_MAP:
                return f"参数错误: 必须包含 'stakeNo' 和 'frequency' (可选值: {list(Config.FREQ_MAP.keys())})"
            data = bytes([Config.FREQ_MAP[cmd['frequency']]])
            for dev_eui in cmd['stakeNo'].split(','):
                self.chirpstack_client.send_downlink(dev_eui, 10, data)
        return None

    @_api_handler_decorator
    def set_level(self, commands):
        valid_levels = [500, 1000, 2000, 4000, 7000]
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'level']) or cmd['level'] not in valid_levels:
                return f"参数错误: 必须包含 'stakeNo' 和 'level' (可选值: {valid_levels})"
            level = cmd['level']
            data = bytes([(level >> 8) & 0xFF, level & 0xFF])
            for dev_eui in cmd['stakeNo'].split(','):
                self.chirpstack_client.send_downlink(dev_eui, 13, data)
        return None

    @_api_handler_decorator
    def set_manner(self, commands):
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'manner']) or cmd['manner'] not in [0, 1]:
                return "参数错误: 必须包含 'stakeNo' 和 'manner' (0或1)"
            data = bytes([cmd['manner']])
            for dev_eui in cmd['stakeNo'].split(','):
                self.chirpstack_client.send_downlink(dev_eui, 12, data)
        return None
        
    @_api_handler_decorator
    def set_switch(self, commands):
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'switch']) or cmd['switch'] not in [0, 1]:
                return "参数错误: 必须包含 'stakeNo' 和 'switch' (0或1)"
            data = bytes([cmd['switch']])
            for dev_eui in cmd['stakeNo'].split(','):
                self.chirpstack_client.send_downlink(dev_eui, 14, data)
        return None
        
    @_api_handler_decorator
    def overall_setting(self, commands):
        # 此处可添加更详细的参数验证...
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'color', 'frequency', 'level', 'manner']):
                return "参数错误: 缺少 'stakeNo', 'color', 'frequency', 'level', 'manner' 中一项或多项"
            payload = bytes([
                cmd['color'], Config.FREQ_MAP[cmd['frequency']],
                (cmd['level'] >> 8) & 0xFF, cmd['level'] & 0xFF,
                cmd['manner']
            ])
            for dev_eui in cmd['stakeNo'].split(','):
                self.chirpstack_client.send_downlink(dev_eui, 15, payload)
        return None

    @_api_handler_decorator
    def set_flashing_lights_switch(self, commands):
        for cmd in commands:
            if not all(k in cmd for k in ['stakeNo', 'switch']) or cmd['switch'] not in [0, 1]:
                return "参数错误: 必须包含 'stakeNo' 和 'switch' (0或1)"
            f_port = 17 if cmd['switch'] == 0 else 16
            data = bytes([cmd['switch']])
            for dev_eui in cmd['stakeNo'].split(','):
                self.chirpstack_client.send_downlink(dev_eui, f_port, data)
        return None