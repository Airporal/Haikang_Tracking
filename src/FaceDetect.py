import ctypes
from HCUSBSDK import *
import os
import time
from DevClass import devClass
import tkinter
from tkinter import Button

class myHaikang(devClass):
    def __init__(self):
        super().__init__()
        print("myHaikang init")

    def load_local_dll(self):
        self.add_a_dll(USB_DLL_TYPE.ENUM_DLL_PLAYCTRL_PATH,self.libPath + b'\\PlayCtrl\\PlayCtrl.dll', "PlayCtrl")
        self.add_a_dll(USB_DLL_TYPE.ENUM_DLL_PLAYCTRL_PATH, self.libPath + b'\\libusb-1.0.dll', "Libusb")
    # 开始预览
    def StartWork(self):
        # 初始化活体检测算法
        struConfigInputInfo = USB_CONFIG_INPUT_INFO()
        self.usbSDK.USB_Control(self.m_lUserID,3012,byref(struConfigInputInfo))
        time.sleep(10)
        struVideoParam,struVideoCapacityParam = self.get_video_param("USB_GET_VIDEO_CAP")

        self.set_video_param(struVideoParam,w=3840, h=2160, fps=30,useAudio=0,sharpness=50,focus=764,AutoFocus=1)

        self.get_video_param()

        # todo: 开始预览取流
        if sys_platform == 'windows':
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
            struPreviewParam.bYUVCallback = 0

            # 开始预览并且设置回调函数回调获取实时流数据
            self.lRealPlayHandle = self.usbSDK.USB_StartPreview(self.m_lUserID, byref(struPreviewParam))
            if self.lRealPlayHandle < 0:
                print('FAILED USB_StartPreview, error code is: %d' % self.usbSDK.USB_StartPreview())
                exit()
            pFaceDetectParm = USB_FACE_DETECT_PARAM()
            def detect_callback(lport, struFDResultInfo, pUser):
                print(f"detect_callback：{struFDResultInfo.dwFaceTotalNum}")
            fnFDE = FDExtenResultCallBack(detect_callback)
            pFaceDetectParm.fnFDExtenResultCallBack = fnFDE
            pFaceDetectParm.bySnapMode = 0
            self.usbSDK.USB_StartFaceDetect(self.m_lUserID,byref(pFaceDetectParm))
            self.get_detect_result()
            # show Windows
            self.win.mainloop()

            self.usbSDK.USB_StartFaceDetect()

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

            time.sleep(5)
    def StopWork(self):
        if self.usbSDK.USB_StopChannel(self.m_lUserID, self.lRealPlayHandle):
            print("停止预览 SUCCESS!")
        else:
            dwErrorCode = self.usbSDK.USB_GetLastError()
            print("停止预览 Failed！ErrorCode = ", dwErrorCode)
    def get_detect_result(self):
        struConfigInputInfo = USB_CONFIG_INPUT_INFO()
        struConfigOutputInfo = USB_CONFIG_OUTPUT_INFO()

        struFROutput = USB_FR_LIVE_PARAM()
        struFRInput = USB_LIVE_COND_INFO()
        struConfigOutputInfo.lpOutBuffer = ctypes.c_void_p(ctypes.addressof(struFROutput))
        struConfigOutputInfo.dwOutBufferSize = sizeof(struFROutput)
        struConfigInputInfo.lpInBuffer = ctypes.c_void_p(ctypes.addressof(struFRInput))
        struConfigInputInfo.dwInBufferSize = sizeof(struFRInput)
        if self.usbSDK.USB_GetDeviceConfig(self.m_lUserID,  dwCommand['USB_GET_LIVEDETECT'],
                                           byref(struConfigInputInfo), byref(struConfigOutputInfo)):
            print(f"活体检测结果：{struFROutput.stTargetLiveOut.strLiveInfo.nLiveStatus},置信度：{struFROutput.stTargetLiveOut.strLiveInfo.fLiveConfidence}")
        else:
            self.get_usb_error_msg()

if __name__ == '__main__':
    dev = myHaikang()
    dev.load_local_dll()
    dev.init_sdk()
    dev.GeneralSetting()
    dev.EnumDevices()  # 枚举设备
    dev.USBLogin()  # 登录
    dev.StartWork() # 开始工作
    dev.StopWork()  # 停止工作
    dev.USBLogout()  # 登出
    dev.USBCleanup()  # 反初始化SDK
