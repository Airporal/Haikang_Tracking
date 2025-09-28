"""
    无UI，根据aruco码定位机器人，并跟踪
"""
from ctypes.wintypes import DWORD
from HCNetSDK import *
from PlayCtrlSDK import *
from normal_detector import NormalDetector
import cv2
import time
from utils import get_frame_jpeg_cv,calculate_dynamic_sleep
from baseSdk import devClass
import os
import datetime
CONFIG_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(CONFIG_DIR)
IMG_DIR = os.path.join(PROJECT_DIR, "img")
DATA = datetime.datetime.now().strftime("%Y-%m-%d")
# 生成保存目录
save_dir = os.path.join(IMG_DIR, DATA)
os.makedirs(save_dir, exist_ok=True)

class netPlay(devClass):
    def __init__(self, use_Playctrl = True):
        super().__init__(use_Playctrl)
        self.jpeg_ready = False
        self.init_flag = False
        self.init_detect_flag = False
        self.track = False  # 是否跟随目标
        self.move_position = True  # 用于mannual模式控制移动
        self.please_update_extrinsic = False  # 用于记录是否需要更新外参
        self.update_exterinsic_threshold = 2  # 用于记录更新外参的aruco码数量阈值
        
        self.FuncDecCB = None
        self.running = True  # 程序运行标志
        self.prev_frame_time = 0  # 上一帧时间
        self.new_frame_time = 0  # 当前帧时间
        self.history_centers = []  # 存储历史中心点坐标
        self.bias = [] # 保存像素偏差量
        self.max_history = 10  # 最大历史记录数
        
        self.threshold = 100  # 跟随阈值,像素偏差小于此值则不调整
        self.start_threshold = 300 # 启动跟踪阈值，像素偏差大于此阈值，则开启跟踪
        self.stop_threshold = 100 # 停止跟踪阈值，像素偏差小于此阈值，则不再跟踪
        # 初始化检测器，同时初始化相机内参和机器人初始位置
        self.detector = NormalDetector(row=25,col=53)  
        self.dynamic_sleep = 0.02  # 动态休眠时间
        self.frame = None         # ui显示的当前帧
        self.origin_frame = None  # 用于保存图片
        
        self.fps = 0
        self.center = (0,0)
        self.number = 0
        self.mapped_points =[
            [591.2625, 412.5, 1],
            [591.2625, 712.5, 1],
            [461.3595, 712.5, 1],
            [461.3595, 412.5, 1]
        ]
        
    def StartWork(self):
        # 用于确保系统头只处理一次
        @CFUNCTYPE(None, c_long, DWORD, POINTER(c_ubyte), DWORD, c_void_p)
        def RealDataCallBack_V30(lRealHandle, dwDataType, pBuffer, dwBufSize, pUser):
            if dwDataType == NET_DVR_SYSHEAD and not self.init_flag:
                self.init_flag = True
                if self.PlayCtrl_Port.value < 0:
                    if not self.Playctrldll.PlayM4_GetPort(byref(self.PlayCtrl_Port)):
                        print("❌ 获取播放通道失败")
                        return
                    print(f"✅ 播放通道号: {self.PlayCtrl_Port.value}")

                if not self.Playctrldll.PlayM4_SetStreamOpenMode(self.PlayCtrl_Port, 0):
                    print("❌ 设置流模式失败")
                    return
                else:
                    print("✅ 设置实时流成功")

                # 打开流
                if not self.Playctrldll.PlayM4_OpenStream(
                        self.PlayCtrl_Port, None, 0, 2 * 1024 * 1024
                ):
                    print("❌ 打开流失败")
                    self.get_play_error_msg()
                    return
                else:
                    print("✅ 打开流成功")

                # 解码回调函数
                @CFUNCTYPE(None, c_long, POINTER(c_ubyte), c_long, c_long, c_long, c_void_p)
                def DecCBFun(nPort, pBuf, nSize, nWidth, nHeight, nUser):
                    if nSize > 0:
                        self.jpeg_ready = True
                    else:
                        print("WAITING...")

                self.DecCBFun = DecCBFun
                if not self.Playctrldll.PlayM4_SetDecCallBackExMend(
                        self.PlayCtrl_Port, self.DecCBFun, None, 0, None
                ):
                    print("❌ 设置解码回调失败")
                    return
                else:
                    print("✅ 设置解码回调成功")

                if not self.Playctrldll.PlayM4_Play(self.PlayCtrl_Port, 0):
                    print("❌ 播放失败")
                    self.get_play_error_msg()
                    return
                else:
                    print("✅ 播放器已启动")

            elif dwDataType == NET_DVR_STREAMDATA:
                if self.init_flag and self.PlayCtrl_Port.value != -1 and dwBufSize > 0:
                    buf_ptr = ctypes.cast(pBuffer, POINTER(c_ubyte))

                    for attempt in range(3):  # 最多重试3次
                        ok = self.Playctrldll.PlayM4_InputData(
                            self.PlayCtrl_Port, buf_ptr, dwBufSize
                        )
                        if ok:
                            return
                        else:
                            err = self.Playctrldll.PlayM4_GetLastError(self.PlayCtrl_Port)
                            if err == 11:  # 缓冲区满
                                print(f"⚠️ 播放库缓冲区满（第 {attempt + 1} 次），等待...")
                                time.sleep(0.005)
                            else:
                                print(f"❌ InputData失败，错误码: {err}")
                                break
                else:
                    print("未初始化或参数无效")
            else:
                print(f"其它数据类型: {dwDataType}, 大小: {dwBufSize}")

        # 注册回调并开启实时预览
        self.RealDataCB = RealDataCallBack_V30
        preview_info = NET_DVR_PREVIEWINFO()
        preview_info.lChannel = 1
        preview_info.dwStreamType = 0  # 主码流
        preview_info.dwLinkMode = 0  # TCP
        preview_info.hPlayWnd = 0
        preview_info.bBlocked = 1
        preview_info.dwDisplayBufNum = 1

        self.lRealPlayHandle = self.Netsdk.NET_DVR_RealPlay_V40(
            self.lUserId, byref(preview_info), self.RealDataCB, None
        )

        if self.lRealPlayHandle < 0:
            print("❌ RealPlay_V40 启动失败")
            self.get_net_error_msg()
            return
        print("✅ RealPlay_V40 启动成功")

        print("等待解码器准备图像数据...")
        for _ in range(30):  # 最多等待3秒
            if self.jpeg_ready:
                print("✅ 解码器已准备好")
                break
            time.sleep(0.1)
        if not self.jpeg_ready:
            print("❌ 解码器3秒内未准备好，GetJPEG 会失败")
            return
        self.prev_frame_time = time.time()
        try:
            cv2.namedWindow(f"Hikvision", cv2.WINDOW_NORMAL)
            dx = 0
            dy = 0
            now_positions = [] # 4x3 idx u v
            while self.running:
                frame = get_frame_jpeg_cv(self.Playctrldll,self.PlayCtrl_Port)
                if frame is None:
                    print("⚠️ 抓图失败，跳过帧")
                    continue
                if not self.init_detect_flag: # 第一帧显示需要初始化
                    # None 表示没有更新成功，同时初始化外参矩阵
                    init_marker_list, init_marker_dict, show_img = self.detector.init_extrinsic(frame)
                    self.init_detect_flag = True
                    now_positions = self.detector.get_now_positions()
                    continue
                self.new_frame_time = time.time()
                self.origin_frame = frame.copy()
                # 角点检测 marker_list 4x4 idx x y z
                marker_list, marker_dict, show_img = self.detector.detect_markers(frame)
                center_pix = self.detector.get_center_pix()
                self.bias = self.detector.get_bias()
                if marker_list is None:
                    continue
                if self.track:
                    # 刚动完，需要更新外参
                    try:
                        m = self.detector.update_extrinsic_from_lstsq(marker_list, now_positions)
                        if m is None:
                            print("继续移动")
                            self.track_target() # 移动
                            # cv2.putText(show_img, f"bias:{centers[0]}x{centers[1]}", (int(center_real_position[0]), int(center_real_position[1])-10), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 255, 0), 8)
                            cv2.imshow("Hikvision", show_img)
                            if cv2.waitKey(3) & 0xFF == ord('q'):
                                    break
                            continue
                    except:
                        print("更新外参失败！")
                # 应用当前外参进行映射估算真实位置 4x3
                mapped_points = self.detector.apply_affine_transform(marker_list)
                now_positions = self.detector.get_now_positions()
                # 计算精度
                # real_position = self.detector.get_real_positions(dx,dy)
                # self.detector.accuracy_estimate(real_position,now_positions)
                # 判断是否需要更新移动 track,bias,center_real_position,centers
                self.track, bias, center_real_position, centers = self.detector.position_check(now_positions.copy(),debug=True)
                
                if self.track:
                    self.track_target() # 移动
                self.history_centers.append(centers)
                if len(self.history_centers)> self.max_history:
                    self.history_centers.pop(0)
                wast_time = time.time()-self.new_frame_time
                self.freq = int(1/(self.new_frame_time-self.prev_frame_time))
                self.prev_frame_time = self.new_frame_time
                # print(center_real_position)
                cv2.circle(show_img,(show_img.shape[1]//2,show_img.shape[0]//2),5,(0,0,255),3)
                cv2.rectangle(show_img,(show_img.shape[1]//2-self.start_threshold,show_img.shape[0]//2-self.start_threshold),
                              (show_img.shape[1]//2+self.start_threshold,show_img.shape[0]//2+self.start_threshold),(255,0,0),3)
                cv2.rectangle(show_img,(show_img.shape[1]//2-self.stop_threshold,show_img.shape[0]//2-self.stop_threshold),
                              (show_img.shape[1]//2+self.stop_threshold,show_img.shape[0]//2+self.stop_threshold),(255,0,0),3)
                # cv2.rectangle(show_img,(int(center_real_position[0])-200,int(center_real_position[1])-200),(int(center_real_position[0])+200,int(center_real_position[1])+200),(0,0,255),3)
                cv2.putText(show_img, f"track:{self.track} bias:{self.bias[0]}x{self.bias[1]},centers:{center_real_position}", (int(center_real_position[0]), int(center_real_position[1])-10), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 255, 0), 8)
                cv2.rectangle(show_img,(int(center_pix[0])-200,int(center_pix[1])-200),(int(center_pix[0])+200,int(center_pix[1])+200),(0,255,0),3)

                cv2.imshow("Hikvision", show_img)
                if cv2.waitKey(3) & 0xFF == ord('q'):
                        break               
        finally:
            pass

    # shape 1080x1920
    def track_target(self):
        # 按下跟随按钮，自动跟踪到stop_threshold, 然后track变为False, 当大于threshold时重新True
        dx = self.bias[0]
        dy = self.bias[1]
        command = None
        # if abs(dx)>self.threshold or abs(dy)>self.threshold:
        self.dynamic_sleep = calculate_dynamic_sleep(dx,dy,200,0.1,0.8)
        if dx<-self.threshold and dy<-self.threshold:
            command = UP_LEFT
        elif dx>self.threshold and dy<-self.threshold:
            command = UP_RIGHT
        elif dx<-self.threshold and dy>self.threshold:
            command = DOWN_LEFT
        elif dx>self.threshold and dy>self.threshold:
            command = DOWN_RIGHT
        elif dx < -self.threshold:
            command = PAN_LEFT
        elif dx > self.threshold:
            command = PAN_RIGHT
        elif dy < -self.threshold:
            command = TILT_UP
        elif dy > self.threshold:
            command = TILT_DOWN
        if command is not None:
            if self.Netsdk.NET_DVR_PTZControl(self.lRealPlayHandle, command, 0):  # 开始
                time.sleep(self.dynamic_sleep)
                self.Netsdk.NET_DVR_PTZControl(self.lRealPlayHandle, command, 1)  # 停止
            else:
                self.get_net_error_msg()
        
    def StopWork(self):
        if self.lRealPlayHandle > -1:
            self.Netsdk.NET_DVR_StopRealPlay(self.lRealPlayHandle)
        if self.PlayCtrl_Port.value > -1:
            self.Playctrldll.PlayM4_Stop(self.PlayCtrl_Port)
            self.Playctrldll.PlayM4_CloseStream(self.PlayCtrl_Port)
            self.Playctrldll.PlayM4_FreePort(self.PlayCtrl_Port)
            self.PlayCtrl_Port = c_long(-1)

if __name__ == '__main__':
    dev = netPlay()  # 初始化参数 + 加载dll
    dev.init_sdk()  # 初始化sdk
    dev.NetLogin()  # 登录设备
    dev.GeneralSetting()   # 设置日志和播放库通道
    dev.StartWork()  # 执行工作
    dev.StopWork()  # 停止预览
    dev.NetLogout()  # 登出设备
    dev.NetCleanup()  # 释放资源