
from ctypes.wintypes import DWORD
from os import utime

from HCNetSDK import *
from PlayCtrlSDK import *
from normal_detector import NormalDetector
import cv2
import time
from utils import get_frame_bmp,get_frame_jpeg_cv,get_frame_jpeg_auto,frame_mode_set,calculate_dynamic_sleep
from baseSdk import devClass
from videoApp import VideoApp
import argparse
args = argparse.ArgumentParser()
args.add_argument("--model", type=str, default="boosting", help="模型选择，默认为boosting")
args.add_argument("--use_UI", type=bool, default=True, help="是否使用UI界面，默认为True")
args.add_argument("--frame_mode", type=int, default=1, help="取流模式 0: 从bmp取流 1: 从jpeg取流 2:自适应 ")
args = args.parse_args()

class netPlay(devClass):
    def __init__(self, use_UI = True, use_Playctrl = True, model = "boosting",frame_mode=1):
        super().__init__(use_Playctrl)
        self.jpeg_ready = False
        self.init_flag = False
        self.begin_cv_flag = False
        self.track = False  # 是否跟随目标
        self.auto = False  # 是否自动跟踪
        self.save_position = True  # 用于记录移动相机后是否完成初始位置的markers标记
        self.please_update_extrinsic = False  # 用于记录是否需要更新外参
        self.update_exterinsic_threshold = 2  # 用于记录更新外参的aruco码数量阈值
        
        self.app = None  # UI界面
        self.FuncDecCB = None
        self.use_UI = use_UI
        self.running = True  # 程序运行标志
        self.prev_frame_time = 0  # 上一帧时间
        self.new_frame_time = 0  # 当前帧时间
        self.n = 0
        self.history_centers = []  # 存储历史中心点坐标
        self.max_history = 10  # 最大历史记录数

        self.threshold = 20  # 跟随阈值,像素偏差小于此值则不调整
        self.detector = NormalDetector(model=model, from_video=False)  # 初始化检测器
        self.dynamic_sleep = 0.01  # 动态休眠时间
        self.frame = None
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
        if self.use_UI:
            self.app = VideoApp(
                use_camera=False,
                frame_provider=self.frame_provider,
                track_handler=self.track_handler,
                exit_handler=self.exit_handler,
                auto_handle=self.auto_handle
            )
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
            if not self.use_UI:
                cv2.namedWindow(f"Hikvision", cv2.WINDOW_NORMAL)
            while self.running:
                mapped_points = []
                frame = get_frame_jpeg_cv(self.Playctrldll,self.PlayCtrl_Port)
                if frame is None:
                    print("⚠️ 抓图失败，跳过帧")
                    continue
                if not self.begin_cv_flag: # 第一帧显示需要初始化
                    # None 表示没有更新成功
                    init_marker_dict = self.detector.init_detector_from_frame(frame,manual=True,save_bbox=True)
                    self.begin_cv_flag = True
                    continue
                self.new_frame_time = time.time()
                # if self.n % 3 ==0:
                # 最新的一帧，目标框坐标，目标框中心点，四个aruco码映射后的坐标
                # 当track为Flase时，如果记录要更新外参，则更新外参
                if self.track is False:
                    # 结束移动后，更新外参后才可以保存新的目标位置
                    if self.please_update_extrinsic:
                        real_positions = self.detector.mylocator.get_now_positions() # 获取记录的真实位置
                        # 识别更新markers的相机坐标系位置，但是不保存当前的估算世界位置，因为外参未更新
                        frame, box, center, mapped_points = self.detector.detect(frame,save_position=False,update=True)
                        # 更新外参
                        # print(f"{real_positions,real_positions.shape}")
                        try:
                            extrinsic_lm = self.detector.mylocator.update_extrinsic_from_lstsq(real_positions=real_positions) 
                        except Exception as e:
                            print(f"更新外参失败：{e}")
                            # print(f"{real_positions,real_positions.shape}")
                            continue
                        self.please_update_extrinsic = False                            
                    else:
                        # 默认情况下，保存新的识别位置和真值位置，同时当检测到aruco码数量大于阈值时，更新外参
                        frame, box, center, mapped_points = self.detector.detect(frame,save_position=True,update=True)
                        if mapped_points is not None and len(mapped_points)>self.update_exterinsic_threshold:
                        # if len(mapped_points)>self.update_exterinsic_threshold:
                            try:
                                real_positions = self.detector.mylocator.get_now_positions() # 获取记录的真实位置
                                extrinsic_lm = self.detector.mylocator.update_extrinsic_from_lstsq(real_positions=real_positions) 
                            except Exception as e:
                                print(f"更新外参失败：{e}")
                                print(f"{real_positions,real_positions.shape}")
                                continue
                else:
                    # 跟踪时，不更新外参，不保存当前的估算世界位置，因为外参未更新
                    frame, box, center, mapped_points = self.detector.detect(frame,save_position=False,update=False)

                # 记录最新的max_history个中心点
                self.history_centers.append((int(center[0]),int(center[1])))
                if len(self.history_centers)> self.max_history:
                    self.history_centers.pop(0)
                wast_time = time.time()-self.new_frame_time
                self.freq = int(1/(self.new_frame_time-self.prev_frame_time))
                self.prev_frame_time = self.new_frame_time
                cv2.putText(frame, f"wast:{wast_time}", (int(box[0]), int(box[1])-10), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 255, 0), 8)
                if self.use_UI:
                    # time.sleep(0.03)
                    # with self.lock:
                    self.app.update_frame()
                    self.app.root.update_idletasks()
                    self.app.root.update()
                    self.frame = frame
                    self.center = (int(center[0]),int(center[1]))
                    self.fps = self.freq
                    if mapped_points is not None:
                        self.number = len(mapped_points)
                        self.mapped_points = mapped_points
                    else:
                         self.number = 0
                         self.mapped_points =[
                            []]
                else:
                    cv2.imshow("Hikvision", frame)
                # print(self.freq,wast_time)
                # if self.number < 4:
                
                self.auto_follow()
                if self.track:
                    self.track_target(frame.shape,center)
                if self.use_UI:
                    if cv2.waitKey(3) & 0xFF == ord('q'):
                        break
        finally:
            pass
            # self.StopWork()
    #     shape 1080x1920
    def track_target(self,shape,box_center):
        cx = shape[1]//2
        cy = shape[0]//2
        dx = box_center[0]-cx
        dy = box_center[1]-cy
        command = None
        if abs(dx)>self.threshold or abs(dy)>self.threshold:
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
            # print(f"{box_center[0]}, {cx}，{dx},{box_center[1]},{cy},{dy},{command},{self.dynamic_sleep}")
            if self.Netsdk.NET_DVR_PTZControl(self.lRealPlayHandle, command, 0):  # 开始
                time.sleep(self.dynamic_sleep)
                # time.sleep(0.09)
                self.Netsdk.NET_DVR_PTZControl(self.lRealPlayHandle, command, 1)  # 停止
            else:
                self.get_net_error_msg()

    def Start_track(self):
        # 跟踪则不跟新真实位置,标记需要更新外参
        self.please_update_extrinsic = True
        self.track = True
        print(f"👌 跟踪按钮被按下{self.track}")
        self.save_position = False
    def Stop_track(self):
        # self.please_update_extrinsic = False
        self.track = False
        self.save_position = True
    def StopWork(self):
        if self.lRealPlayHandle > -1:
            self.Netsdk.NET_DVR_StopRealPlay(self.lRealPlayHandle)
        if self.PlayCtrl_Port.value > -1:
            self.Playctrldll.PlayM4_Stop(self.PlayCtrl_Port)
            self.Playctrldll.PlayM4_CloseStream(self.PlayCtrl_Port)
            self.Playctrldll.PlayM4_FreePort(self.PlayCtrl_Port)
            self.PlayCtrl_Port = c_long(-1)


    def track_handler(self):
        print(f"❤️ 当前track状态：{self.track}")
        if self.track:
            self.Stop_track()
        else:
            self.Start_track()

    def frame_provider(self):

        return self.frame, self.fps, self.center, self.number,self.track,self.mapped_points

    def exit_handler(self):
        self.running = False
        self.StopWork()  # 停止预览
        self.NetLogout()  # 登出设备
        self.NetCleanup()  # 释放资源
        print("✅ 程序退出")
    
    def auto_follow(self):
        # 当开启自动跟踪时，如果目标数量小于4，则开始跟踪，否则停止跟踪
        if self.auto == True:
            if self.number < 4:
                self.Start_track()
                # print(f"开始跟踪{self.track}")
            else:
                self.Stop_track()
                # print(f"停止跟踪{self.track}")
        # print(f"自动跟踪状态：{self.auto,self.track}")
                
    def auto_handle(self):
        # 开启自动跟踪并不一定改变跟踪状态
        print(f"目标数量：{self.number}")
        if self.auto == False:
            self.auto = True
            print("❤️ 自动跟踪已开启")
        else:
            self.auto = False
            self.Stop_track()
            print("❤️ 自动跟踪已关闭 {self.track,self.auto}")

        
if __name__ == '__main__':
    dev = netPlay(use_UI= args.use_UI,model=args.model,frame_mode= frame_mode_set[args.frame_mode])  # 初始化参数 + 加载dll
    dev.init_sdk()  # 初始化sdk
    dev.NetLogin()  # 登录设备
    dev.GeneralSetting()   # 设置日志和播放库通道
    dev.StartWork()  # 执行工作
    # dev.StopWork()  # 停止预览
    # dev.NetLogout()  # 登出设备
    # dev.NetCleanup()  # 释放资源