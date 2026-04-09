"""
    TODO
        实现外部接口     
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
    
    def _calibrate_init(self,init_row,init_col):
        try:
            self.detector = NormalDetector(row=init_row,col=init_col)
            return True
        except:
            print("❌ 初始化检测器失败")
            return False
        
    def _startWork(self):
        """
            打开相机取流
        """
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

    def _initExtrinsic(self, force_reinit = False, show = False):
        if show:
            cv2.namedWindow(f"Hikvision", cv2.WINDOW_NORMAL)
        if self.init_detect_flag and not force_reinit:
            # 已经初始化过了，不需要再次初始化
            return True
        elif self.init_detect_flag and force_reinit:
            # 已经初始化过了，但需要强制重新初始化
            self.init_detect_flag = False        
        init_times = 0
        while init_times < self.max_retry_times:
            frame = get_frame_jpeg_cv(self.Playctrldll,self.PlayCtrl_Port)
            self.frame_shape = frame.shape
            if frame is None:
                print("⚠️ 抓图失败，跳过帧")
                continue
                # 初始化外参矩阵
            try:
                init_marker_list, init_marker_dict, show_img = self.detector.init_extrinsic(frame)
                self.init_detect_flag = True
                now_positions = self.detector.get_now_positions()
                return True
            except:
                print("❌ 初始化检测器失败")
                init_times += 1
                continue
        return False
        
    # shape 1080x1920
    def _track_target(self):
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
        
    def _stopWork(self):
        if self.lRealPlayHandle > -1:
            self.Netsdk.NET_DVR_StopRealPlay(self.lRealPlayHandle)
        if self.PlayCtrl_Port.value > -1:
            self.Playctrldll.PlayM4_Stop(self.PlayCtrl_Port)
            self.Playctrldll.PlayM4_CloseStream(self.PlayCtrl_Port)
            self.Playctrldll.PlayM4_FreePort(self.PlayCtrl_Port)
            self.PlayCtrl_Port = c_long(-1)
    
    def modify_now_positions(self,now_positions):
        """
            根据now_positions映射到行列值，再映射回now_positions
            :param now_positions: 4x3 映射前的位置
            :return: 4x3 校正后的位置
        """
        now_positions = self.detector.modify_legs_position(now_positions)
        
        return now_positions
    
    # 外部调用接口
    def init_haikang(self, init_row, init_col):
        """
            初始化相机并更新外参矩阵
            :param init_row: 机器人中心初始行
            :param init_col: 机器人中心初始列

        """
        # 重置状态，等待首次外参初始化流程在主循环中运行
        self.jpeg_ready = False
        self.init_flag = False
        self.init_detect_flag = False
        self.track = False  # 是否跟随目标
        self.please_update_extrinsic = False  # 用于记录是否需要更新外参
        self.update_exterinsic_threshold = 2  # 用于记录更新外参的aruco码数量阈值
        
        self.FuncDecCB = None
        self.prev_frame_time = 0  # 上一帧时间
        self.new_frame_time = 0  # 当前帧时间
        self.bias = [] # 保存像素偏差量
        
        self.threshold = 100  # 跟随阈值,像素偏差小于此值则不调整
        self.start_threshold = 300 # 启动跟踪阈值，像素偏差大于此阈值，则开启跟踪
        self.stop_threshold = 100 # 停止跟踪阈值，像素偏差小于此阈值，则不再跟踪
        self.max_retry_times = 10  # 最大重试次数
        self.dynamic_sleep = 0.02  # 动态休眠时间
         
        ok = self._calibrate_init(init_row,init_col) # 读取内参，计算机器人初始位置
        if not ok:
            return False
        # 打开相机
        if not self.init_sdk():
            return False
        # 登录设备
        if not self.NetLogin():
            return False
        self.GeneralSetting()  # 设置日志和播放库通道
        self._startWork()  # 执行工作
        return self._initExtrinsic()  # 初始化外参
    
    def _weather_continue_track(self):
        """
            获取当前识别的机器人中心位置
            并判断是否需要跟踪, 更新self.track, self.bias
        """
        detect_times = 0
        while detect_times < self.max_retry_times:
            frame = None
            get_frame_times = 0
            while frame is None and get_frame_times < self.max_retry_times:
                frame = get_frame_jpeg_cv(self.Playctrldll,self.PlayCtrl_Port)
                get_frame_times += 1
            # 角点检测 marker_list 4x4 idx x y z，此处用于更新中点像素位置
            self.detector.detect_markers(frame)
            # 判断当前需要移动还是停止
            self.track, self.bias, _, _ = self.detector.position_check(self.now_positions.copy(),debug=False)
            return self.track
        return self.track
    
    def get_now_center_positions(self,show=False):
        """
            获取当前识别位置，已经使用管板行列校正
            show表示是否显示图像
            更新self.marker_list、self.now_positions用于后续更新外参
            更新self.track, self.bias用于移动相机
            return:
                机器人中心的行列位置
        """
        # 获取当前识别的机器人中心位置
        detect_times = 0
        while detect_times < self.max_retry_times:
            frame = None
            get_frame_times = 0
            while frame is None and get_frame_times < self.max_retry_times:
                frame = get_frame_jpeg_cv(self.Playctrldll,self.PlayCtrl_Port)
                get_frame_times += 1
            # 角点检测 marker_list 4x4 idx x y z
            self.marker_list, marker_dict, show_img = self.detector.detect_markers(frame)
            # 中心像素及其偏差，用于判断是否需要移动相机
            center_pix = self.detector.get_center_pix()
        
            if self.marker_list is None:
                detect_times += 1
                continue

                    
            # 应用当前外参进行映射估算真实足端位置 4x3
            mapped_points = self.detector.apply_affine_transform(self.marker_list)
            now_positions = self.detector.get_now_positions()
            self.now_positions = self.modify_now_positions(now_positions)  # 修正误差
        
            # 判断当前需要移动还是停止
            # 是否track, 中心像素偏差，中心的x、y位置, 中心的行列位置
            self.track, self.bias, center_real_position, centers = self.detector.position_check(self.now_positions.copy(),debug=True)

            if show:
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
            
            return centers
        return None
            
    
    def move_ptc(self, once=False):
        """
            移动ptc, 必须先调用get_now_center_positions立刻调用
            once表示是否单步移动：
                True表示只移动一步，继续移动需要到下一次调用
                False表示持续移动到结束为止
            return:
                True表示移动成功
                False表示移动出错
        """
        if self.track:
            try:
                if once:
                    self._track_target() # 移动一步
                    self.please_update_extrinsic = True
                    return True
                else:
                    # 持续移动到结束为止：
                    while self.track:
                        self._track_target() # 移动一步
                        self._weather_continue_track() # 判断是否继续移动,并更新bias
                    self.please_update_extrinsic = True
                    return True
            except:
                print("❌ 移动失败")
                return False
        return True
        
            
                
    def update_extrinsic(self, now_row=-1, now_col=-1):
        '''
            手动更新外参，由于更新外参需要最新的图像帧，如果相机已经移动了，需要重新识别
            :param now_row: 机器人中心当前行
            :param now_col: 机器人中心当前列
            return:
                True: 更新成功
                False: 更新失败
        '''
        if now_col == -1 or now_row == -1:
            # 默认根据识别位置更新外参
            now_position = self.now_positions
        else:
            # 根据真实位置更新外参
            now_position = self.detector._caculate_legs_position(now_row, now_col)
            
        if not self.please_update_extrinsic:
            # 云台没有移动，不需要重新识别
            try:
                m = self.detector.update_extrinsic_from_lstsq(self.marker_list, now_position)
                if m is None:
                    return False
                return True
            except:
                print("更新外参失败！")
                return False
        else:
            # 云台移动了，需要重新识别
            detect_times = 0
            while detect_times < self.max_retry_times:
                frame = None
                get_frame_times = 0
                while frame is None and get_frame_times < self.max_retry_times:
                    frame = get_frame_jpeg_cv(self.Playctrldll,self.PlayCtrl_Port)
                    get_frame_times += 1
                try:    
                    # 角点检测 marker_list 4x4 idx x y z
                    marker_list, _, _ = self.detector.detect_markers(frame)
                    if marker_list is None:
                        detect_times += 1   
                        continue
                    m = self.detector.update_extrinsic_from_lstsq(marker_list, now_position)
                    if m is not None:
                        self.please_update_extrinsic = False
                        return True
                    else:
                        detect_times += 1   
                except:
                    detect_times += 1   
                    continue
            return False

    
    
    def stop_work(self):
        self._stopWork()  # 停止工作
        self.NetLogout()  # 登出设备
        self.NetCleanup()  # 释放资源
    

if __name__ == '__main__':
    dev = netPlay()  # 初始化参数 + 加载dll
    # 初始化函数
    dev.init_haikang(10, 10)  # 初始化相机并更新外参矩阵
    n = 0
    while n<1000:
        if n % 10 == 0:
            # 获取当前识别的机器人中心位置
            centers = dev.get_now_center_positions(show=False)
            move_flag = dev.move_ptc(once=False)  # 移动ptc,直到抵达中心位置
            ok = dev.update_extrinsic()  # 更新外参
            if centers is not None:
                # 可发送位置
                print(centers)
        print(n)
        n += 1

    dev.stop_work()  # 停止工作