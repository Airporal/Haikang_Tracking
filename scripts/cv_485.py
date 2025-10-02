import serial
import serial.tools.list_ports
import time
import cv2
from normal_detector import NormalDetector
import time
from utils import get_frame_jpeg_cv,calculate_dynamic_sleep
import os
import datetime
from videoApp import VideoApp
CONFIG_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(CONFIG_DIR)
IMG_DIR = os.path.join(PROJECT_DIR, "img")
DATA = datetime.datetime.now().strftime("%Y-%m-%d")
# 生成保存目录
save_dir = os.path.join(IMG_DIR, DATA)
os.makedirs(save_dir, exist_ok=True)
import serial
import serial.tools.list_ports
import threading
import queue
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class ReliablePelcoD:
    def __init__(self, baudrate=9600, timeout=0.2, address=1,
                 inter_frame_delay=0.05, repeat=1, port=None, use_rs485_settings=False):
        """
        inter_frame_delay: 每帧发送后等待的最小时间(s)，用于物理线路释放和接收器切换
        repeat: 每条命令默认重复次数（提高可靠性）
        use_rs485_settings: 如果你的 USB-RS485 适配器能通过 RTS 控制 DE/RE，设为 True
        """
        self.address = address
        self.inter_frame_delay = inter_frame_delay
        self.repeat = max(1, int(repeat))
        self._q = queue.Queue()
        self._stop_event = threading.Event()
        self._sender_thread = None

        self.port = port or self._find_port()
        if not self.port:
            raise RuntimeError("未找到 CH340 RS-485 设备")
        self.ser = serial.Serial(self.port, baudrate=baudrate, timeout=timeout, write_timeout=0.5)

        if use_rs485_settings:
            try:
                self.ser.rs485_mode = serial.rs485.RS485Settings(
                    rts_level_for_tx=True, rts_level_for_rx=False, loopback=False
                )
                logging.info("RS485Settings 已启用（RTS 控制 DE/RE）")
            except Exception as e:
                logging.warning("启用 RS485Settings 失败：%s", e)

        # 启动发送线程
        self._sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self._sender_thread.start()

    def _find_port(self):
        for p in serial.tools.list_ports.comports():
            if 'CH340' in p.description or (p.vid == 0x1A86 and p.pid == 0x7523):
                return p.device
        return None

    def _build_packet(self, cmd1: int, cmd2: int, data1: int = 0, data2: int = 0) -> bytes:
        pkt = bytearray(7)
        pkt[0] = 0xFF
        pkt[1] = self.address & 0xFF
        pkt[2] = cmd1 & 0xFF
        pkt[3] = cmd2 & 0xFF
        pkt[4] = data1 & 0xFF
        pkt[5] = data2 & 0xFF
        pkt[6] = sum(pkt[1:6]) % 256
        return bytes(pkt)

    def send_async(self, cmd1: int, cmd2: int, data1: int = 0, data2: int = 0, repeat: int = None):
        """把要发送的帧放入队列（异步）"""
        if repeat is None:
            repeat = self.repeat
        self._q.put((cmd1, cmd2, data1, data2, int(repeat)))

    def send_sync(self, cmd1: int, cmd2: int, data1: int = 0, data2: int = 0, timeout: float = 2.0, repeat: int = None):
        """
        同步发送：把命令放队列并等待队列被消费（适合测试）
        """
        if repeat is None:
            repeat = self.repeat
        done = threading.Event()
        self._q.put((cmd1, cmd2, data1, data2, int(repeat), done))
        return done.wait(timeout=timeout)

    def _sender_loop(self):
        while not self._stop_event.is_set():
            try:
                item = self._q.get(timeout=0.1)
            except queue.Empty:
                continue

            # 支持两种队列项格式： (cmd1,cmd2,data1,data2,repeat) 或 (cmd1,cmd2,data1,data2,repeat,done_event)
            done_event = None
            if len(item) == 6:
                cmd1, cmd2, data1, data2, repeat, done_event = item
            else:
                cmd1, cmd2, data1, data2, repeat = item

            pkt = self._build_packet(cmd1, cmd2, data1, data2)
            # 重发机制
            success = False
            for i in range(repeat):
                try:
                    # 写入物理串口
                    self.ser.write(pkt)
                    # flush 确保写入内核（并尝试等待发送）
                    try:
                        self.ser.flush()   # wait until data is written to OS buffer / driver
                    except Exception:
                        pass

                    # 等待缓冲区为空（out_waiting 在 pyserial 中表示尚未发送的字节）
                    timeout_deadline = time.time() + 1.0
                    while getattr(self.ser, 'out_waiting', 0) > 0 and time.time() < timeout_deadline:
                        time.sleep(0.001)

                    # 再等待一个短的 inter_frame_delay，确保线路释放（半双工）
                    time.sleep(self.inter_frame_delay)
                    success = True
                except serial.SerialTimeoutException:
                    logging.warning("串口写入超时，重试 %d/%d", i+1, repeat)
                except Exception as e:
                    logging.exception("写串口发生错误: %s", e)
                    break

            # 可选地打印或记录发送的帧（十六进制），便于调试
            logging.debug("发送帧: %s (cmd1=0x%02X cmd2=0x%02X repeat=%d)", pkt.hex(), cmd1, cmd2, repeat)

            if done_event:
                done_event.set()

            self._q.task_done()

    # ---- 简单封装方向命令 ----
    def left(self, speed=0x20):         self.send_async(0x00, 0x04, data1=speed, data2=0)
    def right(self, speed=0x20):        self.send_async(0x00, 0x02, data1=speed, data2=0)
    def up(self, speed=0x20):           self.send_async(0x00, 0x08, data1=0, data2=speed)
    def down(self, speed=0x20):         self.send_async(0x00, 0x10, data1=0, data2=speed)
    def left_up(self, xs=0x20, ys=0x20):self.send_async(0x00, 0x0C, data1=xs, data2=ys)
    def right_up(self, xs=0x20, ys=0x20):self.send_async(0x00, 0x0A, data1=xs, data2=ys)
    def left_down(self, xs=0x20, ys=0x20):self.send_async(0x00, 0x14, data1=xs, data2=ys)
    def right_down(self, xs=0x20, ys=0x20):self.send_async(0x00, 0x12, data1=xs, data2=ys)
    def stop(self):                     self.send_async(0x00, 0x00, 0, 0)

    def close(self):
        logging.info("Stopping sender thread...")
        self._stop_event.set()
        if self._sender_thread:
            self._sender_thread.join(timeout=1.0)
        try:
            self.ser.close()
        except Exception:
            pass
    
class Mydetector():
    def __init__(self):
        self.jpeg_ready = False
        self.init_flag = False
        self.begin_cv_flag = False
        self.track = False  # 是否跟随目标
        self.auto = False  # 是否自动跟踪
        self.auto2 = False # 是否动态跟踪
        self.move_position = True  # 用于mannual模式控制移动
        self.please_update_extrinsic = False  # 用于记录是否需要更新外参
        self.update_exterinsic_threshold = 2  # 用于记录更新外参的aruco码数量阈值
        self.redetect_flag = False  # 用于记录是否需要重新检测
        
        self.app = None  # UI界面
        self.FuncDecCB = None
        self.use_UI = True
        self.running = True  # 程序运行标志
        self.prev_frame_time = 0  # 上一帧时间
        self.new_frame_time = 0  # 当前帧时间
        self.n = 0
        self.history_centers = []  # 存储历史中心点坐标
        self.bias = [] # 保存像素偏差量
        self.max_history = 10  # 最大历史记录数

        self.threshold = 20  # 跟随阈值,像素偏差小于此值则不调整
        self.start_threshold = 30 # 启动跟踪阈值，像素偏差大于此阈值，则开启跟踪
        self.stop_threshold = 10 # 停止跟踪阈值，像素偏差小于此阈值，则不再跟踪
        self.detector = NormalDetector(model="boosting", from_video=False)  # 初始化检测器，同时初始化相机内参和机器人初始位置
        self.dynamic_sleep = 0.01  # 动态休眠时间
        self.frame = None         # ui显示的当前帧
        self.origin_frame = None  # 用于保存图片
        
        self.tracker = ReliablePelcoD(baudrate=9600, inter_frame_delay=0.06, repeat=1, use_rs485_settings=False)
        
        self.show_mark = True # True: 显示具有标记的图像，False: 显示原始图像
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
                auto_handler=self.auto_handler,
                auto2_handler=self.auto2_handler,
                save_handler=self.save_handler,
                mark_handler=self.mark_handler,
                detect_handler=self.detect_handler
            )
        self.cap = cv2.VideoCapture(1)
        # 设置分辨率（可选）
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        if not self.cap.isOpened():
            print("无法打开摄像头")
            return
        self.prev_frame_time = time.time()
        while self.running:
            mapped_points = []
            ret, frame = self.cap.read()
            if not ret:
                print("无法读取视频帧")
                continue
            if not self.begin_cv_flag:
                # None 表示没有更新成功，同时初始化外参矩阵
                init_marker_dict = self.detector.init_detector_from_frame(frame,manual=True,save_bbox=True)
                self.begin_cv_flag = True
                mapped_points = self.detector.mylocator.get_now_positions()
                continue
            self.new_frame_time = time.time()
            self.origin_frame = frame.copy()
            if self.redetect_flag:
                # 目标丢失了，需要重新检测目标，此过程只对目标框重新识别
                if self.redetect_Not_finised:
                    if self.please_update_extrinsic:
                        print("❌ 相机外参变动，可能无法精确跟踪目标！")
                    self.detector.redetect(frame)
                    self.redetect_Not_finised = False
                    print("✅ 重新跟踪目标结束，请复位跟踪按钮")
                    continue
                # 根据模板重新匹配目标
                else:
                    print("✅ 重新跟踪目标结束，请复位跟踪按钮")
            if self.track is False:
                # 结束移动后，更新外参后才可以保存新的目标位置
                if self.please_update_extrinsic:
                    real_positions = self.detector.mylocator.get_now_positions() # 获取记录的真实位置，save_position中更新的真实位置
                    # 识别更新markers的相机坐标系位置，但是不保存当前的估算世界位置，因为外参未更新
                    frame, box, center, mapped_points,mark_frame = self.detector.detect(frame,save_position=False,update=True)
                    # 更新外参
                    # print(f"{real_positions,real_positions.shape}")
                    if mapped_points is not None and len(mapped_points)>self.update_exterinsic_threshold:
                        try:
                            extrinsic_lm = self.detector.mylocator.update_extrinsic_from_lstsq(real_positions=real_positions) 
                        except Exception as e:
                            print(f"更新外参失败：{e}")
                            # print(f"{real_positions,real_positions.shape}")
                            continue
                        self.please_update_extrinsic = False
                    # 没有aruco码, 无法更新外参，此时持续更新外参
                    else:
                        print("❌ 请注意，未识别到aruco码，无法更新外参！！ ")
                else:
                    # 默认情况下，保存新的识别位置和真值位置，同时当检测到aruco码数量大于阈值时，更新外参
                    frame, box, center, mapped_points,mark_frame  = self.detector.detect(frame,save_position=True,update=True)
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
                        print(f"❌ 请注意，未识别到aruco码或aruco码数量小于阈值，无法更新外参！！！ {mapped_points}")
            else:
                # 跟踪时，不更新外参，不保存当前的估算世界位置，因为外参未更新
                frame, box, center, mapped_points,mark_frame  = self.detector.detect(frame,save_position=False,update=False)
            # 记录最新的max_history个中心点
            # 记录最新的max_history个中心点
            self.history_centers.append((int(center[0]),int(center[1])))
            if len(self.history_centers)> self.max_history:
                self.history_centers.pop(0)
            cx = frame.shape[1]//2
            cy = frame.shape[0]//2
            dx = int(center[0])-cx
            dy = int(center[1])-cy
            self.bias = [dx,dy]
            wast_time = time.time()-self.new_frame_time
            self.freq = int(1/(self.new_frame_time-self.prev_frame_time))
            self.prev_frame_time = self.new_frame_time
            cv2.putText(mark_frame, f"bias:{dx}x{dy}", (int(box[0]), int(box[1])-10), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 255, 0), 8)
            if self.use_UI:
                # time.sleep(0.03)
                # with self.lock:
                self.app.update_frame()
                self.app.root.update_idletasks()
                self.app.root.update()
                # 控制显示画面是否显示标记，用于检测错误
                if self.show_mark:
                    self.frame = mark_frame
                else:
                    self.frame = frame
                self.center = (int(center[0]),int(center[1]))
                self.fps = self.freq
                if mapped_points is not None:
                    # 显示锚点个数和位置，位置是识别的真实位置，如果相机外参未更新则不一定正确
                    self.number = len(mapped_points)
                    self.mapped_points = mapped_points
                else:
                        self.number = 0
                        self.mapped_points =[[]]
            else:
                cv2.imshow("Hikvision", frame)
            self.auto_follow()
            if self.auto2:
                self.auto2_checker()
            if self.track:
                self.track_target(frame.shape,center)
            if self.use_UI:
                if cv2.waitKey(3) & 0xFF == ord('q'):
                    break
    def track_target(self,shape,box_center):
        
        dx = self.bias[0]
        dy = self.bias[1]
        command = None
        if abs(dx)>self.threshold or abs(dy)>self.threshold:
            self.dynamic_sleep = calculate_dynamic_sleep(dx,dy,1000,0.1,0.8)
            if dx<-self.threshold and dy<-self.threshold:
                self.tracker.left_up()
                print(f"LEFT_UP:{self.dynamic_sleep}")
            elif dx>self.threshold and dy<-self.threshold:
                self.tracker.right_up()
                print(f"RIGHT_UP:{self.dynamic_sleep}")
            elif dx<-self.threshold and dy>self.threshold:
                self.tracker.left_down()
                print(f"LEFT_DOWN:{self.dynamic_sleep}")
            elif dx>self.threshold and dy>self.threshold:
                self.tracker.right_down()
                print(f"RIGHT_DOWN:{self.dynamic_sleep}")
            elif dx < -self.threshold:
                self.tracker.left()
                print(f"LEFT:{self.dynamic_sleep}")
            elif dx > self.threshold:
                self.tracker.right()
                print(f"RIGHT:{self.dynamic_sleep}")
            elif dy < -self.threshold:
                self.tracker.up()
                print(f"UP:{self.dynamic_sleep}")
            elif dy > self.threshold:
                self.tracker.down()
                print(f"DOWN:{self.dynamic_sleep}")
            time.sleep(self.dynamic_sleep)
            self.tracker.stop()

    def Start_track(self):
        # 跟踪则不跟新真实位置,标记需要更新外参
        self.please_update_extrinsic = True
        self.track = True
        print(f"👌 跟踪按钮被按下{self.track}")
        
    def Stop_track(self):
        self.track = False
        
    def StopWork(self):
        self.cap.release()

    def track_handler(self):
        print(f"❤️ 当前track状态：{self.track}")
        if self.track:
            self.Stop_track()
        else:
            # 开启时，默认移动
            self.Start_track()

    def mark_handler(self):
        # 更该显示的图像
        self.show_mark = not self.show_mark

    def frame_provider(self):
        return self.frame, self.fps, self.center, self.number,self.track,self.mapped_points

    def exit_handler(self):
        self.running = False
        self.StopWork()  # 停止预览
        print("✅ 程序退出")
    
    def detect_handler(self):
        """
            丢失目标必然无法更新外参，此时如果相机处于持续静止状态，表示外参正确，则重新识别目标，否则需要手动更新外参
        """
        if self.redetect_flag is False:
            self.redetect_flag = True
            self.redetect_Not_finised = True
            print("❌ 目标丢失，开始重新识别目标")
        else:
            self.redetect_flag = False

    
    def save_handler(self):
        if self.origin_frame is not None:
            # 用整数时间戳命名
            timestamp = int(time.time() * 1000)
            filename = f"{timestamp}.jpg"
            img_path = os.path.join(save_dir, filename)
            success = cv2.imwrite(img_path, self.origin_frame)
            if success:
                print(f"拍照成功，保存到 {img_path}, size: {self.origin_frame.shape}")
            else:
                print(f"保存失败，请检查路径: {img_path}")
        else:
            print("没有图像数据")
    
    def auto_follow(self):
        # 当开启自动跟踪时，如果目标数量小于4，则开始跟踪，否则停止跟踪
        if self.auto == True:
            if self.number < 4:
                self.Start_track()
            else:
                self.Stop_track()

                
    def auto_handler(self):
        # 开启自动跟踪并不一定改变跟踪状态
        print(f"目标数量：{self.number}")
        if self.auto == False:
            self.auto = True
            print("❤️ 自动跟踪已开启")
        else:
            self.auto = False
            self.Stop_track()
            print(f"❤️ 自动跟踪已关闭 {self.track,self.auto}")

    def auto2_checker(self):
        """
            当低于停止阈值时，切换状态
        """
        dx = self.bias[0]
        dy = self.bias[1]
        if abs(dx)<self.stop_threshold and abs(dy)<self.stop_threshold:
            # 小于停止阈值，停止跟踪
            self.Stop_track()
        if abs(dx)>self.start_threshold or abs(dy)>self.start_threshold:
            # 超过启动阈值，开始跟踪，直到小于停止阈值
            if self.track is False:
                self.Start_track()
            self.threshold = self.stop_threshold
            print(f"设置阈值: {self.threshold}")
            
    def auto2_handler(self):
        # 开启动态跟踪模式
        print(f"偏离量：{self.bias}")
        if self.auto2 == False:
            self.auto2 = True
            self.Start_track()
            print("❤️ 自动2跟踪已开启")
        else:
            self.auto2 = False
            if self.track:
                self.Stop_track()
            self.threshold = 20
            print(f"❤️ 自动跟踪2已关闭 {self.track,self.auto2,self.threshold }")

# ------------------- 测试 -------------------
if __name__ == "__main__":
    # ctrl = ReliablePelcoD(baudrate=9600, inter_frame_delay=0.06, repeat=1, use_rs485_settings=False)
    # ctrl.up(0x30)
    # time.sleep(1.2)
    # # ctrl.stop()
    # # ctrl.left_down(0x20, 0x20)
    # time.sleep(2.0)
    # ctrl.stop()
    # ctrl.close()
    dev = Mydetector()
    dev.StartWork()
    dev.StopWork()