from twisted.internet import reactor,protocol
import threading
import time
import logging
import re

class GetPlcData(threading.Thread):
    """
    通过三菱MC协议与PLC通信的线程类
    功能：定期读取PLC寄存器数据，当数据与预设值匹配时触发事件
    """
    def __init__(self,sPlcIP,nPlcPort,nInterval=0.5,logging_logger=None):
        """
        初始化PLC数据获取线程
        
        参数:
            sPlcIP: PLC的IP地址
            nPlcPort: PLC的端口号
            nInterval: 读取间隔时间(秒)，默认0.5秒
            logging_logger: 日志记录器，如为None则自动创建
        """
        super().__init__()
        self.lock = threading.Lock()  # 线程锁，用于数据同步
        self.takeActionTrigger=threading.Event()  # 动作触发事件
        self.currentValue=0  # 当前读取到的PLC数据值
        self.setMoniterElementFlag=False
        self.elementChanging=False
        # 日志初始化
        if logging_logger is None:
            formmater =logging.Formatter("%(asctime)s|%(message)s")
            consoleHandler = logging.StreamHandler()
            consoleHandler.setFormatter(formmater)
            saveHandler=logging.FileHandler('./GetPlcData.log')
            saveHandler.setFormatter(formmater)
            self.logger=logging.getLogger('GetPlcData')
            self.logger.setLevel(logging.INFO)
            self.logger.addHandler(consoleHandler)            
            self.logger.addHandler(saveHandler)
            self.logging_logger='GetPlcData'
        else:
            self.logging_logger=logging_logger
            self.logger=logging.getLogger(self.logging_logger)
            
        # 参数赋值
        self.PlcIP =sPlcIP
        self.PlcPort =nPlcPort

        self.nInterval=nInterval
        
        # 三菱PLC元件类型与地址映射字典
        # 格式: '元件类型': (类型十六进制代码, 地址进制)
        self.Type2HexAddr={
            'SM':(b'\x91',10),   # 特殊继电器
            'SD':(b'\xA9',10),   # 特殊寄存器
            'X':(b'\x9C',16),    # 输入继电器
            'Y':(b'\x9D',16),    # 输出继电器
            'M':(b'\x90',10),    # 辅助继电器
            'L':(b'\x92',10),    # 锁存继电器
            'F':(b'\x93',10),    # 报警器
            'V':(b'\x94',10),    # 边沿继电器
            'B':(b'\xA0',16),    # 链接继电器
            'D':(b'\xA8',10),    # 数据寄存器
            'W':(b'\xB4',16),    # 链接寄存器
            'TS':(b'\xC1',10),   # 定时器触点
            'TC':(b'\xC0',10),   # 定时器线圈
            'TN':(b'\xC2',10),   # 定时器当前值
            'SS':(b'\xC7',10),   # 累计定时器触点
            'SC':(b'\xC6',10),   # 累计定时器线圈
            'SN':(b'\xC8',10),   # 累计定时器当前值
            'CS':(b'\xC4',10),   # 计数器触点
            'CC':(b'\xC3',10),   # 计数器线圈
            'CN':(b'\xC5',10),   # 计数器当前值
            'SB':(b'\xA1',16),   # 链接特殊继电器
            'SW':(b'\xB5',16),   # 链接特殊寄存器
            'S':(b'\x98',10),    # 步进继电器
            'DX':(b'\xA2',16),   # 直接输入继电器
            'DY':(b'\xA3',16),   # 直接输出继电器
            'Z':(b'\xCC',10),    # 变址寄存器
            'R':(b'\xAF',10),    # 文件寄存器
            'ZR':(b'\xB0',16),   # 文件寄存器
        }
    def setMoniterElement(self,targetElementAddr,targetElementValue,targetElementEffectiveMask=0xffff):
        """
        设置监控的软原件地址和触发目标值
        
        参数:
            targetElementAddr: 目标元件地址(如"D100", "M200"等)
            targetElementValue: 预设的目标值(16位)
            targetElementEffectiveMask: 数据有效掩码，默认0xFFFF(全掩码)
        """       
        with self.lock: 
            self.targetElementValue=targetElementValue & 0xffff  # 确保目标值在16位范围内
            self.targetElementAddr=targetElementAddr
            self.targetElementEffectiveMask=targetElementEffectiveMask

            flag,elementTypeHexCode, elementStartAddr=self.judgment(self.targetElementAddr)

            if flag:
                self.elementTypeHexCode=elementTypeHexCode
                self.elementStartAddr=elementStartAddr
                self.setMoniterElementFlag=True
                self.elementChanging=True
            else:
                self.logger.error(f"目标元件地址解析失败(16进制字母开头的地址需要在前面加0): {self.targetElementAddr}")
    def Wait(self,timeout_time=None):
        """
        进行等待直到目标软原件值与目标值匹配，或者超时时间到
        
        参数:
            timeout_time: 超时时间
        """           
        self.takeActionTrigger.clear()
        retval=self.takeActionTrigger.wait(timeout_time)
        if retval:
            self.takeActionTrigger.clear()
        return retval


    # 类变量：控制线程运行状态
    isRunning=True
        
    class MCProtocol(protocol.Protocol):
        """
        Twisted协议类，处理与PLC的MC协议通信
        """
        def __init__(self,factory,getPlcDataObj):
            """
            初始化MC协议处理器
            
            参数:
                factory: LoopClientFactory实例
                getPlcDataObj: 外部GetPlcData线程对象
            """
            self.factory=factory
            self.is_waiting_response=False  # 等待响应标志
            # 构建MC协议读取消息帧(读取1个字)
            # self.message=b'\x50\x00\x00\xFF\xFF\x03\x00\x0C\x00\x10\x00\x01\x04\x00\x00' + \
            #             getPlcDataObj.elementStartAddr + \
            #             getPlcDataObj.elementTypeHexCode + \
            #             b'\x01\x00'
            self.waitTimes=0  # 等待计数器
            self.IsConnected=False  # 连接状态标志
            self.getPlcDataObj=getPlcDataObj  # 外部线程对象引用
            self.lastActTriTime=0  # 上次触发时间
            self.lastDataReceived=0  # 上次接收的数据
            self.dataUpdated=False  # 数据更新标志
            self.sendRequestTimeInterval=getPlcDataObj.nInterval  # 发送请求间隔
            self.currentInterval=self.sendRequestTimeInterval  # 当前间隔
            self.logger=logging.getLogger(self.getPlcDataObj.logging_logger)  # 日志记录器
            #self.logger.info(f"MC协议消息帧: {getPlcDataObj.message}")  # 记录消息帧

        def connectionMade(self):
            """TCP连接建立时的回调方法"""
            self.logger.info("已连接至PLC！")
            self.IsConnected=True
            self.buffer=b""  # 初始化接收缓冲区
            self._send_next_request()  # 开始发送请求循环

        def ActivateTrigger(self,currentValue):
            """
            激活触发事件
            
            参数:
                currentValue: 当前读取到的PLC数据值
            """
            with self.getPlcDataObj.lock:
                if not self.getPlcDataObj.elementChanging:
                    self.logger.info("触发takeActionTrigger")
                    self.getPlcDataObj.currentValue=currentValue
                    self.getPlcDataObj.takeActionTrigger.set()  # 设置触发事件
                    self.lastActTriTime=time.time()  # 记录触发时间

        def dataReceived(self, data):
            """
            数据接收处理函数
            
            参数:
                data: 从PLC接收到的原始数据
            """
            self.logger.debug(f"接收到消息：{data}")
            try:
                self.buffer+=data  # 将数据添加到缓冲区
                
                # 检查是否收到完整帧头
                if len(self.buffer)>=9:
                    if self.buffer[0:7] == b'\xD0\x00\x00\xFF\xFF\x03\x00':
                        datalendata=self.buffer[7:9]
                        datalen=int.from_bytes(datalendata,byteorder='little', signed=False)
                        
                        # 检查是否收到完整数据帧
                        if len(self.buffer)>=datalen+9:
                            if datalen>=2:
                                dataEndCodeByte=self.buffer[9:11]
                                dataEndCode=int.from_bytes(dataEndCodeByte,byteorder='little', signed=False)
                                
                                if dataEndCode==0:  # 结束代码为0表示通信正常
                                    if datalen==4:  # 期望的数据长度(1个字=2字节，加上结束代码共4字节)
                                        dataReceivedByte=self.buffer[11:13]
                                        dataReceived=int.from_bytes(dataReceivedByte,byteorder='little', signed=False)
                                        
                                        # 检查数据是否更新
                                        if self.lastDataReceived!=dataReceived:
                                            self.lastDataReceived=dataReceived
                                            self.dataUpdated=True
                                            
                                        # 检查数据是否匹配预设值(应用掩码)
                                        if self.dataUpdated and \
                                           (dataReceived & self.getPlcDataObj.targetElementEffectiveMask) == \
                                           self.getPlcDataObj.targetElementValue:
                                            self.ActivateTrigger(dataReceived)  # 触发动作
                                            self.dataUpdated=False
                                    else:
                                        self.logger.error("接收到的数据比预期多！")
                                else:
                                    self.logger.error(f"与PLC通讯出错！结束代码: {dataEndCode}")
                            else:
                                self.logger.error("接收到的声称数据长度小于2，这不合理！")
                                
                            self.buffer=b""  # 清空缓冲区
                            self.is_waiting_response =False  # 重置等待响应标志
                    else:
                        self.logger.error("检测到数据不合法！")
                        self.buffer=b""  # 清空缓冲区
                        self.is_waiting_response =False
            except Exception as e:
                self.logger.error(f"接受PLC数据处理程序出错！{e}")
            
        def connectionLost(self, reason = ...):
            """TCP连接断开时的回调方法"""
            self.logger.debug("connectionLost")
            self.IsConnected=False
            self.factory.retry_connection()  # 尝试重新连接

        def _send_next_request(self):
            """发送下一个请求到PLC"""
            if GetPlcData.isRunning:
                if self.IsConnected:
                    if not self.is_waiting_response:
                        with self.getPlcDataObj.lock:
                            self.message=b'\x50\x00\x00\xFF\xFF\x03\x00\x0C\x00\x10\x00\x01\x04\x00\x00' + \
                            self.getPlcDataObj.elementStartAddr + \
                            self.getPlcDataObj.elementTypeHexCode + \
                            b'\x01\x00'
                            self.logger.debug(f"发送请求:{self.message}")
                            try:
                                self.transport.write(self.message)  # 发送MC协议请求消息
                                self.getPlcDataObj.elementChanging=False
                                self.getPlcDataObj.takeActionTrigger.clear()
                            finally:
                                self.buffer=b""  # 初始化缓冲区
                                self.is_waiting_response = True
                    else:
                        # 等待响应超时处理
                        if self.waitTimes<=100:
                            self.waitTimes+=1
                        else:
                            self.logger.error("等待接收信息超时，重置信号，下次开始重发信息。")
                            self.buffer=b""  # 初始化缓冲区
                            self.waitTimes=0
                            self.is_waiting_response=False
                
                # 安排下一次请求        
                reactor.callLater(self.currentInterval,self._send_next_request)
                if self.currentInterval!=self.sendRequestTimeInterval:
                    self.currentInterval=self.sendRequestTimeInterval
            else:
                # 停止运行时的清理工作
                try:
                    if self.transport:
                        self.transport.loseConnection()
                    self.factory.stop_retries()  # 停止工厂重试
                finally:
                    reactor.callFromThread(reactor.stop)  # 安全停止Reactor

    class LoopClientFactory(protocol.ClientFactory):
        """
        Twisted客户端工厂类，管理PLC连接
        """
        def __init__(self,getPlcDataObj):
            """
            初始化客户端工厂
            
            参数:
                getPlcDataObj: 外部GetPlcData线程对象
            """
            self.addrIP=getPlcDataObj.PlcIP
            self.addrPort=getPlcDataObj.PlcPort
            self.connector = None  # 用于存储连接器
            self.getPlcDataObj=getPlcDataObj
            self.logger=logging.getLogger(self.getPlcDataObj.logging_logger)

        def buildProtocol(self, addr):
            """创建协议实例"""
            self.logger.info("buildProtocol")
            return GetPlcData.MCProtocol(self,self.getPlcDataObj)
            
        def startedConnecting(self, connector):
            """开始连接时的回调"""
            self.connector = connector
            
        def retry_connection(self):
            """重连机制"""
            if GetPlcData.isRunning:
                reactor.callLater(2,reactor.connectTCP,self.addrIP, self.addrPort, self)
            else:
                reactor.callFromThread(reactor.stop)
                
        def clientConnectionFailed(self, connector, reason):
            """客户端连接失败时的回调"""
            self.logger.error("连接失败")
            self.retry_connection()  # 尝试重新连接
            
        def stop_retries(self):
            """停止所有重试和连接"""
            if self.connector:
                self.connector.disconnect()

    def judgment(self,text):
        """
        解析PLC元件地址字符串
        
        参数:
            text: 元件地址字符串(如"D100", "M200")
            
        返回:
            (成功标志, 元件类型十六进制代码, 元件起始地址字节)
        """
        pattern = r'^([A-Za-z]{1,2})([0-9][0-9A-Fa-f]{0,4})$'
        match = re.match(pattern, text)
        
        if match:
            letters = match.group(1)  # 提取字母部分(元件类型)
            numbers = match.group(2)  # 提取数字部分(元件地址)
            
            elementType=letters.upper()  # 转换为大写
            if elementType in self.Type2HexAddr:
                n_number=int(numbers,self.Type2HexAddr[elementType][1])  # 按进制转换地址
                if n_number<=0xffffff and n_number>=0:  # 地址范围检查(3字节)
                    elementTypeHexCode = self.Type2HexAddr[elementType][0]
                    elementStartAddr = n_number.to_bytes(3, byteorder='little')  # 小端字节序
            return True, elementTypeHexCode, elementStartAddr
        else:
            return False, None, None

    def run(self):
        """
        线程主运行方法
        """
        # 解析目标元件地址
        if self.setMoniterElementFlag:
            try:
                factory=GetPlcData.LoopClientFactory(self)
                reactor.connectTCP(factory.addrIP, factory.addrPort, factory)
                reactor.run(installSignalHandlers=0)  # 运行Twisted reactor(不安装信号处理)
            finally:
                GetPlcData.isRunning = False
                #self.takeActionTrigger.set()  # 确保触发事件被设置
                self.logger.info("Reactor已完全停止")
        else:
            self.logger.error("运行失败。需要先用setMoniterElement设置需要监视的软原件点")

    @staticmethod
    def stop_connection():
        """
        静态方法：外部调用停止所有连接
        """
        GetPlcData.isRunning = False
        reactor.callFromThread(reactor.stop)