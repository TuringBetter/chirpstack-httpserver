# LoRaWAN LED 控制通信协议说明文档

本协议定义了基于 LoRaWAN 的 LED 控制指令规范，终端设备通过解析 `fPort` 和 `payload` 字段实现 LED 的颜色、亮度、闪烁等控制功能。

## 通信概述

- 使用 LoRaWAN 下行数据帧传输控制指令
- `fPort` 用于区分指令类型
- `payload` 为二进制格式数据，终端解析后执行控制

---

## fPort 分配

| fPort | 功能描述                                               |
|-------|--------------------------------------------------------|
| 10    | 设置 LED 闪烁频率（30Hz / 60Hz / 120Hz）               |
| 11    | 设置 LED 颜色（红色 / 黄色）                          |
| 12    | 设置 LED 是否闪烁（闪烁 / 常亮）                      |
| 13    | 设置 LED 亮度（500 ~ 7000）                           |
| 20    | 设置为“车辆通过”状态：红色 + 亮度7000 + 120Hz         |
| 21    | 设置为“车辆离开”状态：黄色 + 亮度1000 + 常亮         |

---

## 指令格式说明

### fPort = 10：设置闪烁频率

**Payload 格式**

[ 命令码 (0x01) ][ 频率值 (1 Byte) ]


**频率参数**

| 频率 | 十六进制值 |
|------|------------|
| 30Hz | `0x1E`     |
| 60Hz | `0x3C`     |
| 120Hz| `0x78`     |

**示例**

设置闪烁频率为 60Hz：

- `fPort=10`
- `payload=01 3C`

---

### fPort = 11：设置 LED 颜色

**Payload 格式**

[ 命令码 (0x02) ][ 颜色值 (1 Byte) ]


**颜色参数**

| 颜色   | 值   |
|--------|------|
| 红色   | 0x00 |
| 黄色   | 0x01 |

**示例**

设置为黄色：

- `fPort=11`
- `payload=02 01`

---

### fPort = 12：设置是否闪烁

**Payload 格式**

[ 命令码 (0x03) ][ 状态值 (1 Byte) ]


**闪烁控制参数**

| 状态   | 值   |
|--------|------|
| 闪烁   | 0x00 |
| 常亮   | 0x01 |

**示例**

设置为常亮：

- `fPort=12`
- `payload=03 01`

---

### fPort = 13：设置亮度

**Payload 格式**

[ 命令码 (0x04) ][ 高字节 ][ 低字节 ]


**亮度参数（big-endian）**

| 亮度值 | 十六进制     |
|--------|--------------|
| 500    | `01 F4`      |
| 1000   | `03 E8`      |
| 2000   | `07 D0`      |
| 4000   | `0F A0`      |
| 7000   | `1B 58`      |

**示例**

设置亮度为 7000：

- `fPort=13`
- `payload=04 1B 58`

---

## 组合控制命令

### fPort = 20：车辆通过状态

终端执行：

- 设置颜色为红色
- 设置亮度为 7000
- 设置闪烁频率为 120Hz

**Payload：空**

- `fPort=20`
- `payload=`（无）

---

### fPort = 21：车辆离开状态

终端执行：

- 设置颜色为红色
- 设置亮度为 1000
- 设置为常亮

**Payload：空**

- `fPort=21`
- `payload=`（无）

---
