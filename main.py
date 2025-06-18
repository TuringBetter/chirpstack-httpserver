# main.py
import base64
import json
from typing import List, Optional

from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field

# 从其他模块导入我们已经写好的类
from config import Config
from clients import ChirpstackClient, StatusServerClient

# --- 1. 初始化应用和客户端 ---

# 创建 FastAPI 应用实例
# 我们可以在这里添加标题、版本等信息，这些会显示在自动生成的API文档中
app = FastAPI(
    title="智能交通灯LoRa控制服务",
    description="一个通过LoRaWAN控制和监控交通灯设备的API服务",
    version="1.0.0",
)

# 创建客户端实例，它们将在整个应用生命周期内被共享
# 对于更复杂的应用，可以使用FastAPI的依赖注入系统来管理这些资源
chirpstack_client = ChirpstackClient(Config.CHIRPSTACK_SERVER, Config.API_TOKEN)
status_server_client = StatusServerClient(Config.STATUS_SERVER_BASE_URL)


# --- 2. 定义数据模型 (Pydantic Models) ---
# Pydantic模型用于定义请求和响应的数据结构，FastAPI用它来进行数据验证、转换和生成文档

# ChirpStack上行数据模型
class DeviceInfo(BaseModel):
    dev_eui: str = Field(..., alias='devEui')

class UplinkEvent(BaseModel):
    device_info: DeviceInfo = Field(..., alias='deviceInfo')
    data: str

# API命令通用模型
class BaseCommand(BaseModel):
    stake_no: str = Field(..., alias='stakeNo', description="设备EUI号，多个用逗号分隔")

class SetSwitchCommand(BaseCommand):
    switch: int = Field(..., ge=0, le=1, description="开关状态: 1为开, 0为关")

class SetColorCommand(BaseCommand):
    color: int = Field(..., ge=0, le=1, description="颜色: 1为黄色, 0为红色")

class SetFrequencyCommand(BaseCommand):
    frequency: int = Field(..., description="频率，必须是30, 60, 或120之一")
    def __init__(self, **data):
        if data.get('frequency') not in [30, 60, 120]:
            raise HTTPException(status_code=422, detail="频率值必须是30, 60或120")
        super().__init__(**data)

class SetLevelCommand(BaseCommand):
    level: int = Field(..., description="亮度级别，必须是500, 1000, 2000, 4000, 7000之一")
    def __init__(self, **data):
        if data.get('level') not in [500, 1000, 2000, 4000, 7000]:
            raise HTTPException(status_code=422, detail="亮度值必须是500, 1000, 2000, 4000或7000")
        super().__init__(**data)

class SetMannerCommand(BaseCommand):
    manner: int = Field(..., ge=0, le=1, description="亮灯方式: 1为常亮, 0为闪烁")

class OverallSettingCommand(BaseCommand):
    color: int = Field(..., ge=0, le=1)
    frequency: int
    level: int
    manner: int = Field(..., ge=0, le=1)

    def __init__(self, **data):
        # 在模型初始化时进行交叉验证
        if data.get('frequency') not in [30, 60, 120]:
            raise HTTPException(status_code=422, detail="频率值必须是30, 60或120")
        if data.get('level') not in [500, 1000, 2000, 4000, 7000]:
            raise HTTPException(status_code=422, detail="亮度值必须是500, 1000, 2000, 4000或7000")
        super().__init__(**data)


# --- 3. 定义API端点 (Path Operations) ---

@app.get("/", summary="服务根节点", tags=["通用"])
def read_root():
    """返回服务状态信息"""
    return {"status": "ok", "message": "欢迎使用智能交通灯LoRa控制服务"}

@app.post("/integration/uplink", summary="接收ChirpStack上行数据", tags=["ChirpStack集成"])
def handle_uplink(
    # 这个参数来自 Request Body，FastAPI会自动处理
    uplink_data: UplinkEvent,
    event_type: str = Query(..., alias='event',description="事件类型，由ChirpStack在URL中提供")
    ):


    if event_type != "up":
        return {"status": "ignored", "reason": "不是上行事件"}

    try:
        dev_eui = uplink_data.device_info.dev_eui
        decoded_data = base64.b64decode(uplink_data.data)
        if not decoded_data:
            return {"status": "ignored", "reason": "空数据载荷"}

        cmd_code = decoded_data[0]
        
        if cmd_code == 0x06: # 延迟测量
            chirpstack_client.send_downlink(dev_eui, 1, bytes([0x06]))
        elif cmd_code == 0x07: # 人工报警
            status_server_client.send_warn_info(dev_eui, 1)
        elif cmd_code == 0x08: # 事故报警
            status_server_client.send_warn_info(dev_eui, 2)
        elif cmd_code == 0x09: # 心跳
            status_server_client.send_heartbeat(dev_eui)
        else:
            print(f"收到来自 {dev_eui} 的未知命令码: {hex(cmd_code)}")

    except (KeyError, IndexError, base64.binascii.Error) as e:
        raise HTTPException(status_code=400, detail=f"处理上行数据时出错: {e}")
    
    return {"status": "processed"}

# --- 感应灯控制API ---
API_TAGS = ["感应灯控制"]

@app.post("/api/induction-lights/set-color", summary="设置颜色", tags=API_TAGS)
def set_color(commands: List[SetColorCommand]):
    for cmd in commands:
        data = bytes([cmd.color])
        for dev_eui in cmd.stake_no.split(','):
            chirpstack_client.send_downlink(dev_eui, 11, data)
    return {"message": "颜色设置指令已发送"}

@app.post("/api/induction-lights/set-frequency", summary="设置闪烁频率", tags=API_TAGS)
def set_frequency(commands: List[SetFrequencyCommand]):
    for cmd in commands:
        data = bytes([Config.FREQ_MAP[cmd.frequency]])
        for dev_eui in cmd.stake_no.split(','):
            chirpstack_client.send_downlink(dev_eui, 10, data)
    return {"message": "频率设置指令已发送"}

@app.post("/api/induction-lights/set-level", summary="设置亮度", tags=API_TAGS)
def set_level(commands: List[SetLevelCommand]):
    for cmd in commands:
        level = cmd.level
        data = bytes([(level >> 8) & 0xFF, level & 0xFF])
        for dev_eui in cmd.stake_no.split(','):
            chirpstack_client.send_downlink(dev_eui, 13, data)
    return {"message": "亮度设置指令已发送"}

@app.post("/api/induction-lights/set-manner", summary="设置亮灯方式", tags=API_TAGS)
def set_manner(commands: List[SetMannerCommand]):
    for cmd in commands:
        data = bytes([cmd.manner])
        for dev_eui in cmd.stake_no.split(','):
            chirpstack_client.send_downlink(dev_eui, 12, data)
    return {"message": "亮灯方式设置指令已发送"}

@app.post("/api/induction-lights/set-switch", summary="设备开关控制", tags=API_TAGS)
def set_switch(commands: List[SetSwitchCommand]):
    for cmd in commands:
        data = bytes([cmd.switch])
        for dev_eui in cmd.stake_no.split(','):
            chirpstack_client.send_downlink(dev_eui, 14, data)
    return {"message": "开关控制指令已发送"}

@app.post("/api/induction-lights/overall-setting", summary="整体控制", tags=API_TAGS)
def overall_setting(commands: List[OverallSettingCommand]):
    for cmd in commands:
        payload = bytes([
            cmd.color,
            Config.FREQ_MAP[cmd.frequency],
            (cmd.level >> 8) & 0xFF,
            cmd.level & 0xFF,
            cmd.manner
        ])
        for dev_eui in cmd.stake_no.split(','):
            chirpstack_client.send_downlink(dev_eui, 15, payload)
    return {"message": "整体控制指令已发送"}
