# config.py
import json
from logger import setup_logger

class Config:
    """集中管理所有配置"""
    # 文件路径
    DEV_EUI_FILE = 'DEV_EUI.json'
    IP_DEVICES_FILE = 'ip_devices.json'

    # ChirpStack 配置
    CHIRPSTACK_SERVER = "49.232.192.237:18080"
    API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6IjQyOTVmNTUxLTU5YzEtNGIwOS1iMmRhLTBkNjFmYTQ2YmI1NiIsInR5cCI6ImtleSJ9.cgiNxrWfEuPjgwHOQs6t_wrXzH0q7vC_NoN42Y68r4Q"

    # 状态同步服务器
    STATUS_SERVER_BASE_URL = "http://111.20.150.242:10088"

    # HTTP 服务配置
    HTTP_HOST = '0.0.0.0'
    HTTP_PORT = 10088
    
    # 频率映射
    FREQ_MAP = {30: 0x1E, 60: 0x3C, 120: 0x78}
    
    @staticmethod
    def load_json(filepath):
        """从JSON文件加载数据"""
        logger = setup_logger('Config')
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"错误: 配置文件 {filepath} 未找到。")
            return {}
        except json.JSONDecodeError:
            logger.error(f"错误: 配置文件 {filepath} 格式无效。")
            return {}