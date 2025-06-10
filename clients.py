# clients.py
import grpc
import requests
from datetime import datetime
from chirpstack_api import api
from logger import setup_logger

class ChirpstackClient:
    """封装与ChirpStack gRPC的交互"""
    def __init__(self, server_address, api_token):
        self.logger = setup_logger('ChirpstackClient')
        try:
            channel = grpc.insecure_channel(server_address)
            self.client = api.DeviceServiceStub(channel)
            self.auth_token = [("authorization", f"Bearer {api_token}")]
            self.logger.info("成功连接到 ChirpStack gRPC 服务。")
        except Exception as e:
            self.logger.error(f"连接 ChirpStack gRPC 服务失败: {e}")
            self.client = None

    def send_downlink(self, dev_eui, f_port, data_bytes=None, confirmed=False):
        if not self.client:
            self.logger.error("ChirpStack 客户端未初始化，无法发送下行消息。")
            return None
            
        req = api.EnqueueDeviceQueueItemRequest()
        req.queue_item.dev_eui = dev_eui
        req.queue_item.f_port = f_port
        req.queue_item.confirmed = confirmed
        if data_bytes is not None:
            req.queue_item.data = data_bytes
        
        try:
            resp = self.client.Enqueue(req, metadata=self.auth_token)
            self.logger.info(f"下行消息已入队 -> DEV_EUI: {dev_eui}, FPort: {f_port}, ID: {resp.id}")
            return resp.id
        except grpc.RpcError as e:
            self.logger.error(f"发送下行到 {dev_eui} 失败: {e.details()}")
            return None

class StatusServerClient:
    """封装与状态同步服务器的HTTP交互"""
    def __init__(self, base_url):
        self.base_url = base_url
        self.logger = setup_logger('StatusServerClient')

    def _make_request(self, endpoint, method='GET', params=None, json_data=None):
        url = f"{self.base_url}{endpoint}"
        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=params, timeout=5)
            elif method.upper() == 'POST':
                response = requests.post(url, json=json_data, timeout=5)
            else:
                self.logger.error(f"不支持的HTTP方法: {method}")
                return False
            
            response.raise_for_status() # 如果状态码不是2xx，则引发HTTPError
            
            self.logger.info(f"成功同步到状态服务器: {endpoint}, 参数: {params or json_data}")
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求状态服务器时发生错误: {endpoint}, 错误: {e}")
            return False

    def send_warn_info(self, stake_no, warn_type):
        params = {
            "stakeNo": stake_no,
            "eventDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "warnType": warn_type
        }
        return self._make_request("/warn/warnInfo", params=params)

    def send_heartbeat(self, stake_no):
        data = {
            "stakeNo": stake_no,
            "updateDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "loraStatus": "Online"
        }
        return self._make_request("/equipmentfailure/sendBeat", method='POST', json_data=data)