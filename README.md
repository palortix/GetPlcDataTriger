# GetPlcData - 三菱MC协议PLC通信库

一个基于Python Twisted框架的异步通信库，用于通过三菱MC协议与PLC进行数据交互。当读取的PLC寄存器数据与预设值匹配时，自动触发事件通知。

## 功能特性

- 🔄 **异步通信**: 基于Twisted框架，支持高并发异步操作
- 🧵 **线程安全**: 内置线程锁和事件机制，确保数据同步
- 📊 **多元件支持**: 支持D、M、X、Y等多种三菱PLC元件类型
- 🎯 **值匹配触发**: 可配置预设值、掩码和触发条件
- 📝 **完整日志**: 内置日志记录功能，支持控制台和文件输出
- ⚡ **自动重连**: 网络异常时自动重连机制
- 🔧 **易于扩展**: 模块化设计，易于扩展其他功能

## 安装

### 环境要求

- Python 3.6或更高版本
- 兼容的三菱PLC（支持MC协议）

### 依赖安装

安装核心依赖
```bash
pip install twisted
```

## 快速开始

### 基本用法

```python
from getplcdata import GetPlcData
#创建PLC监控线程
plc_monitor = GetPlcData(
    sPlcIP="192.168.1.100", # PLC IP地址
    nPlcPort=5000, # PLC端口（通常为5000、5001或5002）
    nInterval=0.5, # 读取间隔（秒）
    logging_logger=None # 自定义日志记录器（可选）
    )

plc_monitor.setMoniterElement(
    targetElementAddr="r1", # 目标元件地址
    targetElementValue=100, # 预设触发值
    targetElementEffectiveMask=0xFFFF, # 有效位掩码
)
#启动监控
plc_monitor.start()
#等待触发事件
if plc_monitor.Wait(60): # 等待30秒
    print(f"触发事件！当前值: {plc_monitor.currentValue}")
else:
    print("未在超时时间内触发")
#修改监控对象
plc_monitor.setMoniterElement(
    targetElementAddr="r2", # 目标元件地址
    targetElementValue=200, # 预设触发值
    targetElementEffectiveMask=0xFFFF, # 有效位掩码
)

#等待触发事件
if plc_monitor.Wait(60): # 等待30秒
    print(f"触发事件！当前值: {plc_monitor.currentValue}")
else:
    print("未在超时时间内触发")

#停止监控
GetPlcData.stop_connection()
plc_monitor.join()
```

### 支持的PLC元件类型

| 元件类型 | 说明 | 示例地址 |
|---------|------|----------|
| D | 数据寄存器 | D100, D200 |
| M | 辅助继电器 | M0, M100 |
| X | 输入继电器 | X0, X0A0 |
| Y | 输出继电器 | Y0, Y1B0 |
| SD | 特殊寄存器 | SD100, SD200 |
| SM | 特殊继电器 | SM100 |

完整支持列表请参考源码中的`Type2HexAddr`字典。

## API参考

### GetPlcData类

#### 初始化参数
```python
GetPlcData(sPlcIP, nPlcPort, targetElementAddr, targetElementValue,
    targetElementEffectiveMask=0xFFFF, nInterval=0.5, logging_logger=None)
```
- **sPlcIP** (`str`): PLC的IP地址
- **nPlcPort** (`int`): PLC的端口号
- **targetElementAddr** (`str`): 目标元件地址（如"D100", "M200"）
- **targetElementValue** (`int`): 预设触发值（16位整数）
- **targetElementEffectiveMask** (`int`): 数据有效掩码（默认0xFFFF）
- **nInterval** (`float`): 数据读取间隔，单位秒（默认0.5）
- **logging_logger**: 自定义日志记录器（可选）

#### 主要属性

- `takeActionTrigger` (`threading.Event`): 触发事件对象
- `currentValue` (`int`): 当前读取到的PLC数据值
- `lock` (`threading.Lock`): 线程锁，用于数据同步
- `isRunning` (`classvariable`): 类变量，控制线程运行状态

#### 静态方法

- `stop_connection()`: 停止所有PLC连接和reactor循环

### 元件地址解析规则

地址字符串格式：`<元件类型><地址号>`
- 元件类型：1-2个大写字母（如D、M、X、Y、SD等）
- 地址号：十进制或十六进制数字（十六进制需以字母开头时前加0）

**有效示例**:
- `"D100"` - 数据寄存器100（十进制）
- `"M200"` - 辅助继电器200（十进制）  
- `"X0A"` - 输入继电器10（十六进制）
- `"SD1000"` - 特殊寄存器1000（十进制）

## 故障排除

### 常见问题

1. **连接失败**
   - 检查PLC IP地址和端口是否正确,需要在PLC的以太网的打开设置中设置TCP的MC协议端口。
   - 确认网络连通性（ping测试）
   - 验证PLC的MC协议功能已启用

2. **地址解析错误**
   - 确认元件类型拼写正确
   - 十六进制地址前加0（如"X0A"而不是"XA"）

3. **数据不触发**
   - 检查预设值和掩码设置
   - 确认PLC数据实际变化
   - 查看日志输出获取详细错误信息

## 贡献指南

我们欢迎任何形式的贡献！请阅读以下指南：

### 报告问题
- 使用Issue模板提供详细描述
- 包括PLC型号、Python版本和错误日志
- 提供可复现的示例代码

## 许可证

本项目基于MIT许可证开源 - 查看[LICENSE](LICENSE)文件了解详情。

## 作者

由[palortix]创建和维护。

- 邮箱: [palortix@ghac.cn](mailto:palortix@163.COM)
- GitHub: [palortix](https://github.com/palortix)

## 版本历史

- v1.0.0 (当前)
  - 基础PLC通信功能
  - 值匹配触发机制
  - 多元件类型支持