#这是一个介绍如何使用 GetPlcData的例子程序
import logging
from logging.handlers import TimedRotatingFileHandler
import os
from getplcdata import GetPlcData

def setupLogging():
    os.makedirs('./log/', exist_ok=True)
    consoleHandler = logging.StreamHandler()
    formmater =logging.Formatter("%(asctime)s|%(message)s")
    consoleHandler.setFormatter(formmater)
    for loggername in ('main',):
        logger=logging.getLogger(loggername)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(consoleHandler)
    save_handler = TimedRotatingFileHandler("./log/GetPlcData.log", when="midnight", interval=1)
    save_handler.suffix = "%Y-%m-%d"
    save_handler.setLevel(logging.DEBUG)
    formmater =logging.Formatter("%(asctime)s|%(levelname)-8s|%(name)s|%(filename)s:%(lineno)s|%(message)s")
    save_handler.setFormatter(formmater)
    rootlogger=logging.getLogger()
    rootlogger.addHandler(save_handler)    

if __name__=="__main__":
    setupLogging()
    #创建PLC监控线程
    plc_monitor = GetPlcData(
        sPlcIP="192.168.1.100", # PLC IP地址
        nPlcPort=5000, # PLC端口（通常为5000、5001或5002）
        nInterval=0.5, # 读取间隔（秒）
        logging_logger='main' # 自定义日志记录器（可选）
        )
    
    plc_monitor.setMoniterElement(
        targetElementAddr="D100", # 目标元件地址
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
        targetElementAddr="D200", # 目标元件地址
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
