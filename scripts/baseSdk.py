import ctypes
from ctypes.wintypes import POINT, DWORD

from HCNetSDK import *
import os
import utils
import tkinter
from tkinter import *
from ctypes import *
from HCNetSDK import *
from INFOSTRUCT import *
import threading
from PlayCtrlSDK import *
import queue
import math
from normal_detector import NormalDetector
from PIL import Image
import io
import cv2
import numpy as np
import time

from scripts.utils import calculate_dynamic_sleep

# TODO添加到类中

class devClass:
    def __init__(self,use_Playctrl = True):
        self.Netsdk = None
        self.Playctrldll = None
        self.lRealPlayHandle = None  # 实时预览句柄
        self.use_Playctrl = use_Playctrl  # 是否使用播放库
        self.lUserId = c_long(-1)  # 登录句柄
        self.PlayCtrl_Port = c_long(-1)  # 播放句柄
        self.WINDOWS_FLAG = utils.is_windows()  # 系统环境标识
        self.projectPath, self.libPath, self.logPath = utils.set_path(self.WINDOWS_FLAG) # 跟目录，动态库目录，日志目录
        self.DEV_IP = b'192.168.1.64'
        self.DEV_PORT = 8000
        self.DEV_USER_NAME = b'admin'
        self.DEV_PASSWORD = b'19871273623a'
        self.w = 1920
        self.h = 1080
        self.fps = 60

    def LoadDll(self):
        # 加载基本库
        netsdkdllpath = os.path.join(self.libPath.decode('gbk'), 'HCNetSDK.dll')  # 返回 DLL 的完整路径
        # print("------netsdkdllpath", netsdkdllpath)
        # print("------project_dir", self.projectPath.decode('gbk'))
        dll_dir = os.path.dirname(netsdkdllpath)
        os.chdir(dll_dir)
        self.Netsdk = CDLL(r'./HCNetSDK.dll')
        print("✅ HCNetSDK.dll 加载成功")
        if self.use_Playctrl:
            self.Playctrldll = CDLL(r'./PlayCtrl.dll')  # 加载播放库
            print("✅ PlayCtrl.dll 加载成功")
        # 加载组件库
        if self.WINDOWS_FLAG:
            strPath = os.getcwd().encode('gbk')
            sdk_ComPath = NET_DVR_LOCAL_SDK_PATH()
            sdk_ComPath.sPath = strPath
            self.Netsdk.NET_DVR_SetSDKInitCfg(Load_dll_type['NET_SDK_INIT_CFG_SDK_PATH'], byref(sdk_ComPath))
            self.Netsdk.NET_DVR_SetSDKInitCfg(Load_dll_type['NET_SDK_INIT_CFG_LIBEAY_PATH'], create_string_buffer(strPath + b'\libcrypto-1_1-x64.dll'))
            self.Netsdk.NET_DVR_SetSDKInitCfg(Load_dll_type['NET_SDK_INIT_CFG_SSLEAY_PATH'], create_string_buffer(strPath + b'\libssl-1_1-x64.dll'))
        else:
            strPath = os.getcwd().encode('utf-8')
            sdk_ComPath = NET_DVR_LOCAL_SDK_PATH()
            sdk_ComPath.sPath = strPath
            self.Netsdk.NET_DVR_SetSDKInitCfg(Load_dll_type['NET_SDK_INIT_CFG_SDK_PATH'], byref(sdk_ComPath))
            self.Netsdk.NET_DVR_SetSDKInitCfg(Load_dll_type['NET_SDK_INIT_CFG_LIBEAY_PATH'], create_string_buffer(strPath + b'/libcrypto.so.1.1'))
            self.Netsdk.NET_DVR_SetSDKInitCfg(Load_dll_type['NET_SDK_INIT_CFG_SSLEAY_PATH'], create_string_buffer(strPath + b'/libssl.so.1.1'))
        print("✅ libcrypto.dll & libssl.dll 加载成功")

    def get_net_error_msg(self):
        code = self.Netsdk.NET_DVR_GetLastError()
        self.Netsdk.NET_DVR_GetErrorMsg.argtypes = [POINTER(c_long)]
        self.Netsdk.NET_DVR_GetErrorMsg.restype = c_char_p
        msg_ptr = self.Netsdk.NET_DVR_GetErrorMsg(byref(c_long(code)))
        error_msg = msg_ptr.decode('gbk') if msg_ptr else "未知错误"
        print(f"Error {code}:{error_msg}!")

    def get_play_error_msg(self):
        code = self.Playctrldll.PlayM4_GetLastError(self.PlayCtrl_Port)
        print(f"PlayCtrl Error {code}!")

    def get_all_error_msg(self):
        self.get_net_error_msg()
        # play_Ctrl必须获取通道才能获取错误信息
        if self.PlayCtrl_Port.value != -1:
            self.get_play_error_msg()

    def show_sdk_version(self):
        def decode_version(version_int):
            v1 = (version_int >> 24) & 0xFF
            v2 = (version_int >> 16) & 0xFF
            v3 = (version_int >> 8) & 0xFF
            v4 = version_int & 0xFF
            return f"{v1}.{v2}.{v3}.{v4}"
        net_version = self.Netsdk.NET_DVR_GetSDKVersion()
        if self.use_Playctrl:
            play_version = self.Playctrldll.PlayM4_GetSdkVersion()
            print("✅ 初始化PlayCtrl成功！", decode_version(play_version))
        print("✅ 初始化NetSDK成功！ ", decode_version(net_version))

    def init_sdk(self):
        self.LoadDll()
        if self.Netsdk.NET_DVR_Init():  # 初始化sdk
            self.show_sdk_version()
        else:
            print("❌ SDK初始化失败!")
            self.get_all_error_msg()

    def NetLogin(self):
        login_info = NET_DVR_USER_LOGIN_INFO()
        login_info.bUseAsynLogin = 0
        login_info.sDeviceAddress = self.DEV_IP
        login_info.wPort = self.DEV_PORT
        login_info.sUserName = self.DEV_USER_NAME
        login_info.sPassword = self.DEV_PASSWORD
        device_info = NET_DVR_DEVICEINFO_V40()
        self.lUserId = self.Netsdk.NET_DVR_Login_V40(byref(login_info), byref(device_info))
        if self.lUserId < 0:
            print("✅ 登录失败!")
            self.get_net_error_msg()
            # 释放资源
            self.Netsdk.NET_DVR_Cleanup()
            exit()
        else:
            # TODO 显示设备信息
            print("✅ 登录成功!")
        cfg = NET_DVR_CAMERAPARAMCFG_EX()
        cfg.dwSize = sizeof(cfg)
        re = DWORD(0)
        if self.Netsdk.NET_DVR_GetDVRConfig(self.lUserId, 3368, 2, byref(cfg), sizeof(cfg),byref(re)):
            # print("✅ 获取设备信息成功！场景模式：",sceneMode[cfg.bySceneMode],
            #       "亮度增强比率：",cfg.byBrightCompensate,
            #       "视频输入模式：",cfg.byCaptureModeN,cfg.byCaptureModeP,
            #       "视场角：",cfg.byHorizontalFOV,cfg.byVerticalFOV)
            pass
        else:
            print("❌ 获取设备信息失败!")
            self.get_net_error_msg()


    def GeneralSetting(self, logPath=None):
        # 日志的等级（默认为0）：0-表示关闭日志，1-表示只输出ERROR错误日志，2-输出ERROR错误信息和DEBUG调试信息，3-输出ERROR错误信息、DEBUG调试信息和INFO普通信息等所有信息
        # self.usbSDK.NET_DVR_SetLogToFile(3, b'./SdkLog_Python/', False)
        if logPath is None:
            logPath = self.logPath
        if self.Netsdk.NET_DVR_SetLogToFile(3, (logPath), False):
            print(f'✅ 设置日志目录成功！')
        else:
            print('❌ 设置日志目录失败!')
            self.get_net_error_msg()


    def ptz_control_test(self,command):
        if self.Netsdk.NET_DVR_PTZControl(self.lRealPlayHandle,command, 0):  # 开始

            cv2.waitKey(20)  # 控制时长
            self.Netsdk.NET_DVR_PTZControl(self.lRealPlayHandle, command, 1)  # 停止
        else:
            print("❌ PTZ控制失败!")
            self.get_net_error_msg()

    def StartWork(self):
        pass

    def StopWork(self):
        pass

    def NetLogout(self):
        if self.Netsdk.NET_DVR_Logout(self.lUserId):
            print("✅ Logout Device SUCCESS!")
        else:
            print("❌ Logout Device FAIL!")
            self.get_all_error_msg()
    def NetCleanup(self):
        if self.Netsdk.NET_DVR_Cleanup():
            print("✅ Net_Cleanup SUCCESS!")
        else:
            self.get_all_error_msg()

if __name__ == '__main__':
    dev = devClass()  # 初始化参数 + 加载dll
    dev.init_sdk()  # 初始化sdk
    dev.NetLogin()  # 登录设备
    dev.GeneralSetting()   # 设置日志和播放库通道
    dev.StartWork()  # 执行工作
    dev.StopWork()  # 停止预览
    dev.NetLogout()  # 登出设备
    dev.NetCleanup()  # 释放资源