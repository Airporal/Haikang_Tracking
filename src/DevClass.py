import ctypes
from HCUSBSDK import *
import os


class devClass:
    def __init__(self):
        self.usbSDK = self._LoadSDK()  # 加载sdk库
        self.m_lUserID = -1  # 登录句柄
        self.nDeviceNum = 0  # 设备数量
        self.m_csUserName = b"admin"  # 用户名
        self.m_csPassword = b"19871273623A"  # 密码
        self.szSerialNumber = 'CE07F84C_P0E0501_SN0001'  # 操作设备的序列号
        self.VIP = 0  # 设备VID
        self.PID = 0
        self.lRealPlayHandle = -1  # 预览句柄
        self.wincv = True  # windows环境下的参数
        self.win = True  # 预览窗口
        self.basePath = ''  # 项目根目录
        self.libPath = ''  # 动态库目录
        self.logPath = '' # 日志目录
        self._set_path()  # 设置项目路径

    def _LoadSDK(self):
        usbSDK = None
        try:
            print("usbsdkdllpath: ", usbsdkdllpath)
            usbSDK = load_library(usbsdkdllpath)
        except OSError as e:
            print('动态库加载失败', e)
        return usbSDK
    def _set_path(self):
        if sys_platform == 'windows':
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_dir = os.path.dirname(current_dir)
            basePath = project_dir.encode('gbk')
            libPath = basePath + b'\lib'

        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_dir = os.path.dirname(current_dir)
            basePath = project_dir.encode('utf-8')
            libPath = basePath + b'\lib'

        self.basePath = basePath
        self.libPath = libPath
        self.logPath = self.basePath + b'/SdkLog_Python/'

    def add_a_dll(self, dll_type_enum: USB_DLL_TYPE, dll_path_bytes: bytes, label=""):
        """封装设置 USB_SetSDKLocalCfg 的函数"""
        load_path = USB_LOCAL_LOAD_PATH()
        load_path.emType = dll_type_enum.value
        length = len(dll_path_bytes)
        load_path.byLoadPath[:length] = dll_path_bytes
        if self.usbSDK.USB_SetSDKLocalCfg(USB_LOCAL_CFG_TYPE.ENUM_LOCAL_CFG_TYPE_LOAD_PATH.value,
                                          byref(load_path)):
            print(f'✅ [{label}] DLL Load Success → {dll_path_bytes.decode("gbk")}')
        else:
            print(f'❌ [{label}] DLL Load Failed → {dll_path_bytes.decode("gbk")}')

    def show_sdk_version(self):
        def decode_version(version_int):
            v1 = (version_int >> 24) & 0xFF
            v2 = (version_int >> 16) & 0xFF
            v3 = (version_int >> 8) & 0xFF
            v4 = version_int & 0xFF
            return f"{v1}.{v2}.{v3}.{v4}"
        version = self.usbSDK.USB_GetSDKVersion()
        print("初始化SDK成功！SDK版本:", decode_version(version))

    def get_usb_error_msg(self) -> str:
        code = self.usbSDK.USB_GetLastError()
        self.usbSDK.USB_GetErrorMsg.argtypes = [c_ulong]
        self.usbSDK.USB_GetErrorMsg.restype = c_char_p
        msg_ptr = self.usbSDK.USB_GetErrorMsg(code)
        error_msg = msg_ptr.decode('gbk') if msg_ptr else "未知错误"
        print(f"Error {code}:{error_msg}!")

    def init_sdk(self):
        # TODO: 结合usbSDK.USB_Cleanup反初始化，从而重新尝试初始化
        if self.usbSDK.USB_Init():  # 初始化sdk
            self.show_sdk_version()
        else:
            self.get_usb_error_msg()

    def GeneralSetting(self,logPath=None):
        # 日志的等级（默认为0）：0-表示关闭日志，1-表示只输出ERROR错误日志，2-输出ERROR错误信息和DEBUG调试信息，3-输出ERROR错误信息、DEBUG调试信息和INFO普通信息等所有信息
        # self.usbSDK.NET_DVR_SetLogToFile(3, b'./SdkLog_Python/', False)
        logPath = self.logPath
        self.usbSDK.USB_SetLogToFile(3, (logPath), False)

    def EnumDevices(self):
        self.nDeviceNum = self.usbSDK.USB_GetDeviceCount()  # 获取设备数量
        print("设备数量：", self.nDeviceNum)
        if self.nDeviceNum <= 0:
            print("请检查设备！")
        pStruDeviceInfo = OUT_USB_DEVICE_INFO(self.nDeviceNum)
        if self.usbSDK.USB_EnumDevices(self.nDeviceNum, pStruDeviceInfo):
            # 遍历设备信息
            for i in range(self.nDeviceNum):
                device = pStruDeviceInfo.struDeviceArr[i]
                szManufacturer = str(device.szManufacturer, encoding="utf8").rstrip('\x00')
                szDeviceName = str(device.szDeviceName, encoding="utf8").rstrip('\x00')
                szSerialNumber = str(device.szSerialNumber, encoding="utf8").rstrip('\x00')
                self.szSerialNumber = szSerialNumber
                self.VIP = device.dwVID
                self.PID = device.dwPID
                print(
                    "Device Index:", device.dwIndex,
                    ", dwVID:", device.dwVID,
                    ", dwPID:", device.dwPID,
                    ", szManufacturer:", szManufacturer,
                    ", szDeviceName:", szDeviceName,
                    ", szSerialNumber:", szSerialNumber,
                    "\nAudio:",device.byHaveAudio,

                )
        else:
            self.get_usb_error_msg()

    def USBLogin(self):
        m_struCurUsbLoginInfo = USB_USER_LOGIN_INFO()
        m_struCurUsbLoginInfo.dwSize = m_struCurUsbLoginInfo.__sizeof__()
        m_struCurUsbLoginInfo.dwTimeout = 5000
        m_struCurUsbLoginInfo.dwVID = 11231
        m_struCurUsbLoginInfo.dwPID = 687
        m_struCurUsbLoginInfo.szSerialNumber[:len(self.szSerialNumber)] = self.szSerialNumber.encode('utf-8')
        m_struCurUsbLoginInfo.szUserName[:len(self.m_csUserName)] = self.m_csUserName
        m_struCurUsbLoginInfo.szPassword[:len(self.m_csPassword)] = self.m_csPassword
        m_struCurUsbLoginInfo.byLoginMode = 0 # 0: 需要密码，权限更高
        m_struCurUsbLoginInfo.dwDevIndex = 1

        struDeviceRegRes = USB_DEVICE_REG_RES()
        struDeviceRegRes.dwSize = struDeviceRegRes.__sizeof__()
        self.m_lUserID = self.usbSDK.USB_Login(byref(m_struCurUsbLoginInfo), byref(struDeviceRegRes))
        if self.m_lUserID == -1:
            print("Login Device Failed!")
            self.get_usb_error_msg()
        else:
            print("Login Device Success! UserID = ", self.m_lUserID)

    def USBLogout(self):
        if self.usbSDK.USB_Logout(self.m_lUserID):
            print("Logout Device SUCCESS!")
        else:
            self.get_usb_error_msg()

    def USBCleanup(self):
        if self.usbSDK.USB_Cleanup():
            print("USB_Cleanup SUCCESS!")
        else:
            self.get_usb_error_msg()


    def StartWork(self):
        """
        子类需要重载此方法，开始工作
        """
        pass

    def StopWork(self):
        """
        子类需要重载此方法，停止工作
        """
        pass
    def load_local_dll(self):
        # print("load_local_dll")
        """
            子类需要重载此方法，加载本地的动态库,例如:
            add_a_dll(USB_DLL_TYPE.ENUM_DLL_LIBUSB_PATH,self.libPath + b'\\PlayCtrl\\PlayCtrl.dll', "PlayCtrl")
        """
        pass
    def get_video_param(self,para_name=None):
        struVideoCapacityParam = None
        struConfigInputInfo = USB_CONFIG_INPUT_INFO()
        struConfigOutputInfo = USB_CONFIG_OUTPUT_INFO()

        struVideoPropperty = USB_VIDEO_PROPERTY()
        struConfigOutputInfo.lpOutBuffer = ctypes.c_void_p(ctypes.addressof(struVideoPropperty))
        struConfigOutputInfo.dwOutBufferSize = sizeof(struVideoPropperty)
        if self.usbSDK.USB_GetDeviceConfig(self.m_lUserID,  dwCommand['USB_GET_VIDEO_SHARPNESS'],
                                           byref(struConfigInputInfo), byref(struConfigOutputInfo)):
            print(f"SHARPNESS模式: {'支持自动+手动' if struVideoPropperty.byFlag == 1 else '只支持手动'},{struVideoPropperty.dwValue}")
        else:
            self.get_usb_error_msg()

        struConfigOutputInfo.lpOutBuffer = ctypes.c_void_p(ctypes.addressof(struVideoPropperty))
        struConfigOutputInfo.dwOutBufferSize = sizeof(struVideoPropperty)
        if self.usbSDK.USB_GetDeviceConfig(self.m_lUserID,  dwCommand['USB_GET_VIDEO_FOCUS'],
                                           byref(struConfigInputInfo), byref(struConfigOutputInfo)):
            print(f"Focus模式: {'支持自动+手动' if struVideoPropperty.byFlag == 1 else '只支持手动'},{struVideoPropperty.dwValue}")
        else:
            self.get_usb_error_msg()

        struConfigOutputInfo.lpOutBuffer = ctypes.c_void_p(ctypes.addressof(struVideoPropperty))
        struConfigOutputInfo.dwOutBufferSize = sizeof(struVideoPropperty)
        if self.usbSDK.USB_GetDeviceConfig(self.m_lUserID,  dwCommand['USB_GET_VIDEO_ROLL'],
                                           byref(struConfigInputInfo), byref(struConfigOutputInfo)):
            print(f"roll模式: {'支持自动+手动' if struVideoPropperty.byFlag == 1 else '只支持手动'},{struVideoPropperty.dwValue}")
        else:
            self.get_usb_error_msg()

        struVideoParam = USB_VIDEO_PARAM()
        struConfigOutputInfo.lpOutBuffer = ctypes.c_void_p(ctypes.addressof(struVideoParam))
        struConfigOutputInfo.dwOutBufferSize = sizeof(struVideoParam)
        if self.usbSDK.USB_GetDeviceConfig(self.m_lUserID, dwCommand['USB_GET_VIDEO_PARAM'], byref(struConfigInputInfo),
                                           byref(struConfigOutputInfo)):
            print(f"获取设备视频参数: {struVideoParam.dwWidth}x{struVideoParam.dwHeight}@{struVideoParam.dwFramerate}fps")
        else:
            self.get_usb_error_msg()
        if para_name=="USB_GET_VIDEO_CAP":
            struVideoCapacityParam = USB_VIDEO_CAPACITY()
            struConfigOutputInfo.lpOutBuffer = ctypes.c_void_p(ctypes.addressof(struVideoCapacityParam))
            struConfigOutputInfo.dwOutBufferSize = sizeof(struVideoCapacityParam)
            if self.usbSDK.USB_GetDeviceConfig(self.m_lUserID, dwCommand['USB_GET_VIDEO_CAP'],
                                               byref(struConfigInputInfo),
                                               byref(struConfigOutputInfo)):
                print("正在初始化活体检测...")
            else:
                self.get_usb_error_msg()

        return struVideoParam,struVideoCapacityParam
    def set_video_param(self,struVideoParam:USB_VIDEO_PARAM,w=3840,h=2160,fps=30,useAudio=0,
                        sharpness=50,focus=300,AutoFocus=1):
        struConfigInputInfo = USB_CONFIG_INPUT_INFO()
        struConfigOutputInfo = USB_CONFIG_OUTPUT_INFO()
        # 设置图像参数
        struVideoParam.dwVideoFormat = USB_STREAM_MJPEG
        struVideoParam.dwFramerate = fps
        struVideoParam.dwWidth = w
        struVideoParam.dwHeight = h
        struConfigInputInfo.lpInBuffer = ctypes.c_void_p(ctypes.addressof(struVideoParam))
        struConfigInputInfo.dwInBufferSize = sizeof(struVideoParam)
        if self.usbSDK.USB_SetDeviceConfig(self.m_lUserID, dwCommand['USB_SET_VIDEO_PARAM'], byref(struConfigInputInfo),
                                           byref(struConfigOutputInfo)):
            print("设置设备视频参数 SUCCESS!")
        else:
            self.get_usb_error_msg()
        # 设置视频流类型
        struSrcStreamCfg = USB_SRC_STREAM_CFG()
        struSrcStreamCfg.dwStreamType = USB_STREAM_MJPEG
        struSrcStreamCfg.bUseAudio = useAudio # 0:不使用音频，1:使用音频
        struConfigInputInfo.lpInBuffer = ctypes.c_void_p(ctypes.addressof(struSrcStreamCfg))
        struConfigInputInfo.dwInBufferSize = sizeof(struSrcStreamCfg)
        if self.usbSDK.USB_SetDeviceConfig(self.m_lUserID, dwCommand['USB_SET_SRC_STREAM_TYPE'],
                                           byref(struConfigInputInfo),
                                           byref(struConfigOutputInfo)):
            print("USB_SET_SRC_STREAM_TYPE SUCCESS!")
        else:
            self.get_usb_error_msg()
        #  设置视频清晰度
        struSharpnessCfg = USB_VIDEO_PROPERTY()
        struSharpnessCfg.dwValue = sharpness # 0-100
        struSharpnessCfg.byFlag = 2 # 2:手动，1:自动
        struConfigInputInfo.lpInBuffer = ctypes.c_void_p(ctypes.addressof(struSharpnessCfg))
        struConfigInputInfo.dwInBufferSize = sizeof(struSharpnessCfg)
        if self.usbSDK.USB_SetDeviceConfig(self.m_lUserID, dwCommand['USB_SET_VIDEO_SHARPNESS'],
                                           byref(struConfigInputInfo),
                                           byref(struConfigOutputInfo)):
            print("USB_SET_SRC_VIDEO_SHARPNESS SUCCESS!")
        else:
            self.get_usb_error_msg()
        #  设置聚焦模式
        struFocusCfg = USB_VIDEO_PROPERTY()
        struFocusCfg.dwValue = focus # 焦距
        struFocusCfg.byFlag = AutoFocus # 2:手动，1:自动
        struConfigInputInfo.lpInBuffer = ctypes.c_void_p(ctypes.addressof(struFocusCfg))
        struConfigInputInfo.dwInBufferSize = sizeof(struFocusCfg)
        if self.usbSDK.USB_SetDeviceConfig(self.m_lUserID, dwCommand['USB_SET_VIDEO_FOCUS'],
                                           byref(struConfigInputInfo),
                                           byref(struConfigOutputInfo)):
            print("USB_SET_VIDEO_FOCUS SUCCESS!")
        else:
            self.get_usb_error_msg()
    def exam_device_power(self, property):
        """
        获取设备支持的所有能力，0:不支持，1:支持,2:手动，3:自动
        :return:
        """
        struConfigInputInfo = USB_CONFIG_INPUT_INFO()
        struConfigOutputInfo = USB_CONFIG_OUTPUT_INFO()
        #  设置视频清晰度
        struVideoPropperty = USB_VIDEO_PROPERTY_CAP()
        struConfigOutputInfo.lpOutBuffer = ctypes.c_void_p(ctypes.addressof(struVideoPropperty))
        struConfigOutputInfo.dwOutBufferSize = sizeof(struVideoPropperty)
        if self.usbSDK.USB_SetDeviceConfig(self.m_lUserID, dwCommand['USB_GET_VIDEO_PROPERTY_CAP'],
                                           byref(struConfigInputInfo),
                                           byref(struConfigOutputInfo)):
            print(f"Property:{property}{struVideoPropperty.struPowerLineFrequency.byEnabled}")
        else:
            self.get_usb_error_msg()
# 标准工作流程
if __name__ == '__main__':
    dev = devClass()
    dev.load_local_dll()
    dev.init_sdk()
    dev.GeneralSetting()
    dev.USBLogin()  # 登录
    dev.StartWork() # 开始工作
    dev.StopWork()  # 停止工作
    dev.USBLogout()  # 登出
    dev.USBCleanup()  # 反初始化SDK


