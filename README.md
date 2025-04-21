# LoRaWAN LED 控制通信协议说明文档

## HTTP接口说明

### POST接口

所有POST接口的请求体格式为包含多个`InductionLightCommand`对象的数组：

```json
[
    {
        "stakeNo": "设备编号,可包含多个编号,以逗号分隔,如 DEV_EUI1,DEV_EUI2",
        "color": "颜色设置,取值为 1 表示黄色,0 表示红色",
        "frequency": "频次设置,允许取值为 30、60 或 120",
        "level": "亮灯级别设置,允许取值为 500、1000、2000、4000 或 7000",
        "manner": "亮灯方式设置,取值为 1 表示常亮,0 表示闪烁"
    }
]
```

#### 1. 设置颜色
- 请求格式：`POST /api/induction-lights/set-color`
- 请求体示例：
```json
[
    {
        "stakeNo": "1100000000000001",
        "color": 1
    },
    {
        "stakeNo": "1100000000000002",
        "color": 0
    }
]
```
- 响应格式：
```json
{
    "code": 200,
    "message": "Color setting applied successfully."
}
```

#### 2. 设置频率
- 请求格式：`POST /api/induction-lights/set-frequency`
- 请求体示例：
```json
[
    {
        "stakeNo": "1100000000000001",
        "frequency": 30
    },
    {
        "stakeNo": "1100000000000002",
        "frequency": 60
    }
]
```
- 响应格式：
```json
{
    "code": 200,
    "message": "Frequency setting applied successfully."
}
```

#### 3. 设置亮度
- 请求格式：`POST /api/induction-lights/set-level`
- 请求体示例：
```json
[
    {
        "stakeNo": "1100000000000001",
        "level": 500
    },
    {
        "stakeNo": "1100000000000002",
        "level": 4000
    }
]
```
- 响应格式：
```json
{
    "code": 200,
    "message": "Level setting applied successfully."
}
```

#### 4. 设置亮灯方式
- 请求格式：`POST /api/induction-lights/set-manner`
- 请求体示例：
```json
[
    {
        "stakeNo": "1100000000000001",
        "manner": 1
    },
    {
        "stakeNo": "1100000000000002",
        "manner": 0
    }
]
```
- 响应格式：
```json
{
    "code": 200,
    "message": "Manner setting applied successfully."
}
```

#### 5. 设置设备开关
- 请求格式：`POST /api/induction-lights/set-switch`
- 请求体示例：
```json
[
    {
        "stakeNo": "1100000000000001",
        "switch": 1
    },
    {
        "stakeNo": "1100000000000002",
        "switch": 0
    }
]
```
- 响应格式：
```json
{
    "code": 200,
    "message": "Switch setting applied successfully."
}
```

### 错误响应
所有接口在参数错误或请求失败时会返回如下格式的响应：
```json
{
    "code": 400,
    "message": "错误信息"
}
```

错误信息包括：
- 请求体必须是数组格式
- 无效的JSON格式
- 缺少必要参数
- 参数值超出允许范围
- 不支持的请求路径 