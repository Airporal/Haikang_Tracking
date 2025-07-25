import ctypes
from HCUSBSDK import *
import os
from DevClass import devClass

class myHaikang(devClass):
    def __init__(self):
        super().__init__()
        print("myHaikang init")

    def load_local_dll(self):
        self.add_a_dll(USB_DLL_TYPE.ENUM_DLL_PLAYCTRL_PATH,self.libPath + b'\\PlayCtrl\\PlayCtrl.dll', "PlayCtrl")
        self.add_a_dll(USB_DLL_TYPE.ENUM_DLL_PLAYCTRL_PATH, self.libPath + b'\\libusb-1.0.dll', "Libusb")
    # 开始预览
    def StartWork(self):
        # todo: 获取设备视频参数
        struVideoParam = self.get_video_param()
        self.set_video_param(struVideoParam,w=3840, h=2160, fps=30,useAudio=0,sharpness=50,focus=764,AutoFocus=1)
        self.get_video_param()
        self.move_PAN()
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
    def StopWork(self):
        if self.usbSDK.USB_StopChannel(self.m_lUserID, self.lRealPlayHandle):
            print("停止预览 SUCCESS!")
        else:
            dwErrorCode = self.usbSDK.USB_GetLastError()
            print("停止预览 Failed！ErrorCode = ", dwErrorCode)


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
