import serial
import serial.tools.list_ports
import time
import cv2
from normal_detector import NormalDetector
import time
from utils import get_frame_jpeg_cv,calculate_dynamic_sleep
import os
import datetime
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
        use_rs485_settings: 如 USB-RS485 适配器能通过 RTS 控制 DE/RE，设为 True
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
        
        self.tracker = ReliablePelcoD(baudrate=9600, inter_frame_delay=0.06, repeat=1, use_rs485_settings=False)
        
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
            
    def track_target(self):
        
        dx = self.bias[0]
        dy = self.bias[1]
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

    def StopWork(self):
        self.cap.release()

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