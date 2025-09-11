# -*- coding: utf-8 -*-
# @Time : 2024/11/14 15:12
# @Author : sdk007
import ctypes

from HCUSBSDK import *


class devClass:
    def __init__(self):
        self.usbSDK = self.LoadSDK()  # 加载sdk库
        self.m_lUserID = -1  # 登录句柄
        self.nDeviceNum = 0  # 设备数量
        self.m_csUserName = b"admin"  # 用户名
        self.m_csPassword = b"12345"  # 密码
        self.szSerialNumber = ''  # 操作设备的序列号
        self.lRealPlayHandle = -1  # 预览句柄
        self.wincv = None  # windows环境下的参数
        self.win = None  # 预览窗口
        self.basePath = ''  # 基础路径

    def LoadSDK(self):
        usbSDK = None
        try:
            print("usbsdkdllpath: ", usbsdkdllpath)
            usbSDK = load_library(usbsdkdllpath)
        except OSError as e:
            print('动态库加载失败', e)
        return usbSDK

    # 设置SDK初始化依赖库路径
    def SetSDKInitCfg(self):
        # 设置HCNetSDKCom组件库和SSL库加载路径
        if sys_platform == 'windows':
            basePath = os.getcwd().encode('gbk')
            strPath = basePath + b'\lib'
            playctrlPath = USB_LOCAL_LOAD_PATH()
            playctrlPath.emType = USB_DLL_TYPE.ENUM_DLL_PLAYCTRL_PATH.value  # 设置播放库路径

            path_bytes = strPath + b'\\PlayCtrl\\PlayCtrl.dll'
            path_length = len(path_bytes)
            playctrlPath.byLoadPath[:path_length] = path_bytes
            if self.usbSDK.USB_SetSDKLocalCfg(USB_LOCAL_CFG_TYPE.ENUM_LOCAL_CFG_TYPE_LOAD_PATH.value,
                                              byref(playctrlPath)):
                print('USB_SetSDKLocalCfg: layCtrl Succ')

            libUSBPath = USB_LOCAL_LOAD_PATH()
            libUSBPath.emType = USB_DLL_TYPE.ENUM_DLL_LIBUSB_PATH.value  # 设置 LIBUSB 库路径
            lib_path_bytes = strPath + b'\\libusb-1.0.dll'
            lib_path_len = len(lib_path_bytes)
            libUSBPath.byLoadPath[:lib_path_len] = lib_path_bytes
            if self.usbSDK.USB_SetSDKLocalCfg(USB_LOCAL_CFG_TYPE.ENUM_LOCAL_CFG_TYPE_LOAD_PATH.value,
                                              byref(libUSBPath)):
                print('USB_SetSDKLocalCfg: ibusb Succ')

        else:
            basePath = os.getcwd().encode('utf-8')
            strPath = basePath + b'\lib'
            playctrlPath = USB_LOCAL_LOAD_PATH()
            playctrlPath.emType = USB_DLL_TYPE.ENUM_DLL_PLAYCTRL_PATH.value  # 设置播放库路径
            playctrlPath.byLoadPath = strPath + b'\PlayCtrl\PlayCtrl.dll'
            print('strPath: ', strPath)
            if self.usbSDK.USB_SetSDKLocalCfg(USB_LOCAL_CFG_TYPE.ENUM_LOCAL_CFG_TYPE_LOAD_PATH.value,
                                              byref(playctrlPath)):
                print('USB_SetSDKLocalCfg: layCtrl Succ')

            libUSBPath = USB_LOCAL_LOAD_PATH()
            libUSBPath.emType = USB_DLL_TYPE.ENUM_DLL_LIBUSB_PATH.value  # 设置 LIBUSB 库路径
            libUSBPath.byLoadPath = strPath + b'\libusb-1.0.dll'
            if self.usbSDK.USB_SetSDKLocalCfg(USB_LOCAL_CFG_TYPE.ENUM_LOCAL_CFG_TYPE_LOAD_PATH.value,
                                              byref(libUSBPath)):
                print('NET_DVR_SetSDKInitCfg: ibusb Succ')
        self.basePath = basePath

    # 通用设置，日志
    def GeneralSetting(self):

        # 日志的等级（默认为0）：0-表示关闭日志，1-表示只输出ERROR错误日志，2-输出ERROR错误信息和DEBUG调试信息，3-输出ERROR错误信息、DEBUG调试信息和INFO普通信息等所有信息
        # self.usbSDK.NET_DVR_SetLogToFile(3, b'./SdkLog_Python/', False)
        self.usbSDK.USB_SetLogToFile(3, (self.basePath + b'/SdkLog_Python/'), False)

    # USB枚举设备
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
                print(
                    "Device Index:", device.dwIndex,
                    ", dwVID:", device.dwVID,
                    ", dwPID:", device.dwPID,
                    ", szManufacturer:", szManufacturer,
                    ", szDeviceName:", szDeviceName,
                    ", szSerialNumber:", szSerialNumber
                )
        else:
            print("枚举设备失败！错误码：", self.usbSDK.USB_GetLastError())

    # USB登录设备
    def USBLogin(self):
        m_struCurUsbLoginInfo = USB_USER_LOGIN_INFO()
        m_struCurUsbLoginInfo.dwSize = m_struCurUsbLoginInfo.__sizeof__()
        m_struCurUsbLoginInfo.dwTimeout = 5000
        m_struCurUsbLoginInfo.dwVID = 11231
        m_struCurUsbLoginInfo.dwPID = 650
        m_struCurUsbLoginInfo.szSerialNumber[:len(self.szSerialNumber)] = self.szSerialNumber.encode('utf-8')
        m_struCurUsbLoginInfo.szUserName[:len(self.m_csUserName)] = self.m_csUserName
        m_struCurUsbLoginInfo.szPassword[:len(self.m_csPassword)] = self.m_csPassword
        m_struCurUsbLoginInfo.byLoginMode = 1
        m_struCurUsbLoginInfo.dwDevIndex = 1

        struDeviceRegRes = USB_DEVICE_REG_RES()
        struDeviceRegRes.dwSize = struDeviceRegRes.__sizeof__()
        self.m_lUserID = self.usbSDK.USB_Login(byref(m_struCurUsbLoginInfo), byref(struDeviceRegRes))
        if self.m_lUserID == -1:
            dwErrorCode = self.usbSDK.USB_GetLastError()
            print("Login Device Failed！ErrorCode = ", dwErrorCode)

            if dwErrorCode == USB_ERROR_INACTIVED:
                print("登陆错误：请先激活设备! ")
        else:
            print("Login Device Success! UserID = ", self.m_lUserID)

    # 登出设备
    def USBLogout(self):
        if self.usbSDK.USB_Logout(self.m_lUserID):
            print("Logout Device SUCCESS!")
        else:
            dwErrorCode = self.usbSDK.USB_GetLastError()
            print("Logout Device Failed！ErrorCode = ", dwErrorCode)

    # 开始预览
    def StartPreview(self):
        # todo: 获取设备视频参数
        struConfigInputInfo = USB_CONFIG_INPUT_INFO()
        struConfigOutputInfo = USB_CONFIG_OUTPUT_INFO()
        struVideoParam = USB_VIDEO_PARAM()

        buffer_address = ctypes.addressof(struVideoParam)
        struConfigOutputInfo.lpOutBuffer = ctypes.c_void_p(buffer_address)
        # struConfigOutputInfo.lpOutBuffer = byref(struVideoParam)
        struConfigOutputInfo.dwOutBufferSize = sizeof(struVideoParam)

        if self.usbSDK.USB_GetDeviceConfig(self.m_lUserID, USB_GET_VIDEO_PARAM, byref(struConfigInputInfo),
                                           byref(struConfigOutputInfo)):
            print("获取设备视频参数 SUCCESS!")
        else:
            dwErrorCode = self.usbSDK.USB_GetLastError()
            print("获取设备视频参数 Failed！ErrorCode = ", dwErrorCode)

        # todo: 更新需要设置的参数
        struVideoParam.dwVideoFormat = USB_STREAM_MJPEG
        struVideoParam.dwFramerate = 30
        struVideoParam.dwWidth = 640
        struVideoParam.dwHeight = 480
        buffer_address = ctypes.addressof(struVideoParam)
        struConfigInputInfo.lpInBuffer = ctypes.c_void_p(buffer_address)
        struConfigInputInfo.dwInBufferSize = sizeof(struVideoParam)
        if self.usbSDK.USB_SetDeviceConfig(self.m_lUserID, USB_SET_VIDEO_PARAM, byref(struConfigInputInfo),
                                           byref(struConfigOutputInfo)):
            print("设置设备视频参数 SUCCESS!")
        else:
            dwErrorCode = self.usbSDK.USB_GetLastError()
            print("设置设备视频参数 Failed！ErrorCode = ", dwErrorCode)

        # todo: 设置设备视频参数
        # 更新需要设置的参数
        struSrcStreamCfg = USB_SRC_STREAM_CFG()
        struSrcStreamCfg.dwStreamType = USB_STREAM_MJPEG
        struSrcStreamCfg.bUseAudio = 0
        buffer_address = ctypes.addressof(struSrcStreamCfg)
        struConfigInputInfo.lpInBuffer = ctypes.c_void_p(buffer_address)
        struConfigInputInfo.dwInBufferSize = sizeof(struSrcStreamCfg)
        if self.usbSDK.USB_SetDeviceConfig(self.m_lUserID, USB_SET_SRC_STREAM_TYPE, byref(struConfigInputInfo),
                                           byref(struConfigOutputInfo)):
            print("USB_SET_SRC_STREAM_TYPE SUCCESS!")
        else:
            dwErrorCode = self.usbSDK.USB_GetLastError()
            print("USB_SET_SRC_STREAM_TYPE Failed！ErrorCode = ", dwErrorCode)

        # todo: 开始预览取流
        if sys_platform == 'windows':
            import tkinter
            from tkinter import Button

            # 创建窗口
            self.win = tkinter.Tk()
            # 固定窗口大小
            self.win.resizable(0, 0)
            self.win.overrideredirect(True)

            sw = self.win.winfo_screenwidth()
            # 得到屏幕宽度
            sh = self.win.winfo_screenheight()
            # 得到屏幕高度

            # 窗口宽高
            ww = 512
            wh = 384
            x = (sw - ww) / 2
            y = (sh - wh) / 2
            self.win.geometry("%dx%d+%d+%d" % (ww, wh, x, y))

            # 创建退出按键
            b = Button(self.win, text='退出', command=self.win.quit)
            b.pack()
            # 创建一个Canvas，设置其背景色为白色
            self.wincv = tkinter.Canvas(self.win, bg='white', width=ww, height=wh)
            self.wincv.pack()

            # 开始预览
            struPreviewParam = USB_PREVIEW_PARAM()
            struPreviewParam.dwSize = sizeof(USB_PREVIEW_PARAM)
            struPreviewParam.hWindow = self.wincv.winfo_id()
            struPreviewParam.dwStreamType = USB_STREAM_PS_MJPEG
            struPreviewParam.bUseAudio = 0

            # 开始预览并且设置回调函数回调获取实时流数据
            self.lRealPlayHandle = self.usbSDK.USB_StartPreview(self.m_lUserID, byref(struPreviewParam))
            if self.lRealPlayHandle < 0:
                print('FAILED USB_StartPreview, error code is: %d' % self.usbSDK.USB_StartPreview())
                exit()

            # show Windows
            self.win.mainloop()
        elif sys_platform == 'linux':
            # 开始预览
            struPreviewParam = USB_PREVIEW_PARAM()
            struPreviewParam.dwSize = sizeof(USB_PREVIEW_PARAM)
            struPreviewParam.hWindow = 0
            struPreviewParam.dwStreamType = USB_STREAM_PS_MJPEG
            struPreviewParam.bUseAudio = 0

            # 开始预览并且设置回调函数回调获取实时流数据
            self.lRealPlayHandle = self.usbSDK.USB_StartPreview(self.m_lUserID, byref(struPreviewParam))
            if self.lRealPlayHandle < 0:
                print('FAILED USB_StartPreview, error code is: %d' % self.usbSDK.USB_StartPreview())
                exit()
            # todo：linux环境下如果不直接解码播放的话，可以用USB_StartStreamCallback设置码流回调获取数据。
            import time
            time.sleep(5)

    # 停止预览
    def StopPreview(self):
        if self.usbSDK.USB_StopChannel(self.m_lUserID, self.lRealPlayHandle):
            print("停止预览 SUCCESS!")
        else:
            dwErrorCode = self.usbSDK.USB_GetLastError()
            print("停止预览 Failed！ErrorCode = ", dwErrorCode)


if __name__ == '__main__':
    dev = devClass()
    dev.SetSDKInitCfg()  # 设置SDK初始化依赖库路径
    dev.usbSDK.USB_Init()  # 初始化sdk
    dev.GeneralSetting()  # 通用设置，日志，回调函数等
    dev.EnumDevices()  # 枚举设备
    dev.USBLogin()  # 登录
    dev.StartPreview()  # 预览
    dev.StopPreview()  # 停止预览
    dev.USBLogout()  # 登出
    # # 释放资源
    dev.usbSDK.USB_Cleanup()
