import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2
import time
import os
import datetime
CONFIG_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(CONFIG_DIR)
IMG_DIR = os.path.join(PROJECT_DIR, "img")
DATA = datetime.datetime.now().strftime("%Y-%m-%d")
# 生成保存目录
save_dir = os.path.join(IMG_DIR, DATA)
os.makedirs(save_dir, exist_ok=True)
class VideoApp:
    def __init__(self, use_camera=True, frame_provider=None,track_handler=None,exit_handler=None,auto_handler=None,
                 save_handler=None,mark_handler=None,detect_handler=None,auto2_handler=None):
        self.frame = None
        self.fps_out = 0
        self.center = (0,0)
        self.number = 0
        # 状态机
        self.mode_mechine = "Stop"  # Auto : 当视野受限时自动跟踪，Stop : 停止跟踪，Manual : 手动跟踪目标到中心点 Auto2 :  当偏移中心时自动跟踪，并自动动态停止跟踪
        self.track_flag = False  # 是否正在跟踪目标
        self.show_mark = True  # 是否可视化标记目标
        # 0-1-2-3
        self.mapped_points =[
            [591.2625, 412.5],
            [591.2625, 712.5],
            [461.3595, 712.5],
            [461.3595, 412.5]
        ]

        self.root = tk.Tk()

        self.root.title("OpenCV Video on Canvas")
        # self.root.resizable(0, 0)
        self.track_handler = track_handler
        self.exit_handler = exit_handler
        self.auto_handler = auto_handler
        self.auto2_handler = auto2_handler
        self.save_handler= save_handler
        self.mark_handler = mark_handler
        self.detect_handler = detect_handler
        
        # 居中窗口
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.w ,self.h = 700, 480
        # self.w ,self.h = 1060,1024
        win_w, win_h = self.w, self.h+20
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2 + 1
        self.root.attributes('-alpha', 1)
        self.root.configure(bg='#4B5CC4')
        # self.root.overrideredirect(True)
        self.root.geometry(f"{win_w}x{win_h + 150}+{x}+{y}")
        self.root.resizable(True, True)
        self.root.minsize(700, 480)
        self.root.maxsize(1920, 1080)

        style = ttk.Style()
        style.theme_use("alt")
        style.configure("TButton",background="#065279", foreground="#e9f1f6", font=("微软雅黑", 8),padding=0,relief="flat")
        style.configure("TLabel",background="#4B5CC4", foreground="#e9f1f6", font=("微软雅黑", 10),padding=0,relief="flat")
        # 上方按钮区域
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=5)

        self.btn_quit = ttk.Button(btn_frame, text="退出", command=self.quit_all)
        self.btn_quit.pack(side=tk.LEFT, padx=0.6)

        self.btn_track = ttk.Button(btn_frame, text="跟随", command=self._track_handler)
        self.btn_track.pack(side=tk.LEFT, padx=0.6)
        
        self.btn_auto = ttk.Button(btn_frame, text="自动", command=self._auto_handler)
        self.btn_auto.pack(side=tk.LEFT, padx=0.6)
        
        self.btn_auto2 = ttk.Button(btn_frame, text="动态", command=self._auto2_handler)
        self.btn_auto2.pack(side=tk.LEFT, padx=0.6)
        
        self.btn_save = ttk.Button(btn_frame, text="拍照", command=self._save_handler)
        self.btn_save.pack(side=tk.LEFT, padx=0.6)
        
        self.btn_mark = ttk.Button(btn_frame, text="标记", command=self._mark_handler)
        self.btn_mark.pack(side=tk.LEFT, padx=0.6)
        
        self.btn_detect = ttk.Button(btn_frame, text="识别", command=self._detect_handler)
        self.btn_detect.pack(side=tk.LEFT, padx=0.6)

        # 自定义数据显示
        self.data_label = ttk.Label(self.root, text="等待图像...")
        self.data_label.pack(pady=1)

        # Canvas 显示图像
        self.canvas = tk.Canvas(self.root,
                           width=self.w,
                           height=self.h,
                           bg="#1c1c1c",
                           highlightthickness=0,
                           bd=0,
                           relief='flat',
                           cursor="tcross")
        # self.canvas.pack()
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        
        self.table_frame = ttk.Frame(self.root)
        self.table_frame.pack(pady=5)

        self.marker_table = ttk.Treeview(
            self.table_frame,
            columns=("id", "x", "y", "z"),
            show="headings",
            height=4  # 最多显示4行
        )
        self.marker_table.heading("id", text="ID")
        self.marker_table.heading("x", text="X")
        self.marker_table.heading("y", text="Y")
        self.marker_table.heading("z", text="Z")

        self.marker_table.column("id", width=50, anchor="center")
        self.marker_table.column("x", width=80, anchor="center")
        self.marker_table.column("y", width=80, anchor="center")
        self.marker_table.column("z", width=80, anchor="center")

        self.marker_table.pack()
        # 视频来源
        self.use_camera = use_camera
        self.frame_provider = frame_provider
        self.cap = None
        if self.use_camera:
            self.cap = cv2.VideoCapture(0)

        self.canvas_img_id = None
        self.tracking = False
        self.prev_time = time.time()

        self.update_frame()
    
    def _detect_handler(self):
        if self.detect_handler:
            self.detect_handler()
        else:
            print("错误：未设置检测回调函数")
            
    def _take_photo(self):
        if self.frame is not None:
            # 用整数时间戳命名
            timestamp = int(time.time() * 1000)
            filename = f"{timestamp}.jpg"
            img_path = os.path.join(save_dir, filename)
            success = cv2.imwrite(img_path, self.frame)
            if success:
                print(f"拍照成功，保存到 {img_path}, size: {self.frame.shape}")
            else:
                print(f"保存失败，请检查路径: {img_path}")
        else:
            print("没有图像数据")
            
    def _mark_handler(self):
        # 控制图片是否可视化识别得到的标记信息
        self.show_mark = not self.show_mark
        self.mark_handler()
        if self.show_mark:
            print("可视化标记已打开")
        else:
            print("可视化标记已关闭")
    
    def _save_handler(self):
        if self.save_handler:
            self.save_handler()

    def _track_handler(self):
        if self.track_handler:
            # Auto : 当视野受限时自动跟踪，Auto2 : 将目标限制在stop_threshold与threshold之间，Stop : 停止跟踪，Manual : 手动跟踪目标到中心点
            if self.mode_mechine != "Auto" or self.mode_mechine != "Auto2": 
                # 如果启动自动模式，则此按钮无效
                if self.mode_mechine == "Stop":
                    print("开始手动跟踪")
                    self.mode_mechine = "Manual"
                else:
                    print("停止手动跟踪")
                    self.mode_mechine = "Stop"
                self.track_handler()
                    
        else:
            print("ui初始化失败！")
            self.quit_all()

    def _auto_handler(self):
        # 自动跟随，当arcuo码数量小于4个时，移动相机
        if self.auto_handler:
            if self.mode_mechine != "Auto": # Auto : 当视野受限时自动跟踪，Stop : 停止跟踪，Manual : 手动跟踪目标到中心点
                print("开始自动跟踪")
                self.mode_mechine = "Auto"
                self.auto_handler()
            else:
                print("停止自动跟踪")
                self.mode_mechine = "Stop" # 切换到停止跟踪模式
                self.auto_handler()
        else:
            print("自动跟踪初始化失败！")
            self.quit_all()
    
    def _auto2_handler(self):
        # 自动跟踪，当目标偏移距离大于threshold时，开始跟踪，当目标偏移距离小于stop_threshold时，停止跟踪
        if self.auto2_handler:
            if self.mode_mechine != "Auto2":
                print("开始自动跟踪模式2")
                self.mode_mechine = "Auto2"
                self.auto2_handler()
            else:
                print("停止自动跟踪模式2")
                self.mode_mechine = "Stop"
                self.auto2_handler()
        else:
            print("自动跟踪2初始化失败! ")
            self.quit_all()
    
    def quit_all(self):
        self.root.quit()
        self.root.destroy()
        if self.exit_handler:
            self.exit_handler()

    # 外部调用函数传递图像与信息, 用于从文件中读取
    def set_frame(self,frame=None,fps_out=0,center=(0,0),number=0,track_flag=False,mapped_points=None):
        self.frame = frame
        self.fps_out = fps_out
        self.center = center
        self.number = number
        self.track_flag = track_flag
        self.mapped_points = mapped_points

    def get_frame(self,frame=None):
        # 1.直接从相机获取
        if self.use_camera:
            ret, frame = self.cap.read()
            print(frame.shape)
            if not ret:
                return None,0,0,0,0,np.zeros((4,3))
            return frame,0,0,0,0,np.zeros((4,3))
        else:
            # 2.使用frame_provider获取
            if self.frame_provider:
                return self.frame_provider()
            # 3.从文件读取
            else:
                return self.frame,self.fps_out,self.center,self.number,0,np.zeros((4,3))

    def update_frame(self):
        frame,fps_out,center,number,track_flag,mapped_points = self.get_frame()
        if frame is not None:
            self.frame = frame.copy()

            frame = cv2.resize(frame, (self.w, self.h))
            # 转换图像并显示
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            imgtk = ImageTk.PhotoImage(image=img)

            if self.canvas_img_id is None:
                self.canvas_img_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)
            else:
                self.canvas.itemconfig(self.canvas_img_id, image=imgtk)
            self.canvas.imgtk = imgtk  # 保存引用

            # 更新时间和信息
            now = time.time()
            fps = int(1.0 / (now - self.prev_time + 1e-6))
            self.track_flag = track_flag
            self.prev_time = now
            self.data_label.config(text=
                                   f"FPSOUT: {fps_out}    |    FPS: {fps}    |    CENTER: {center}    |    ArUcoNum: {number}    |    MODE: {self.mode_mechine}    |    Track: {self.track_flag}")
            self.update_marker_table(mapped_points)
        else:
            self.data_label.config(text="等待图像...")

        if self.use_camera:
            self.root.after(10, self.update_frame)

    def update_marker_table(self, marker_positions):
        """
        marker_positions: list of (id, x, y, z)，最多4个, 可能不包含z的数值，若不包含则z空
        """
        # 清空旧数据
        for row in self.marker_table.get_children():
            self.marker_table.delete(row)
        for row in marker_positions:
            self.marker_table.insert("", "end", values=[int(row[0])] + [f"{x:.4f}" for x in row[1:]])
        # # 插入新数据
        # print(marker_positions)
        # for marker in marker_positions[:4]:  # 最多4个
        #     self.marker_table.insert("", "end", values=marker)

    def loop(self):
        self.root.mainloop()

    def __del__(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()


# ✅ 示例：自定义图像来源函数
def custom_frame_provider():
    # 用 OpenCV 生成假图像数据
    frame = 255 * np.ones((960, 1280, 3), dtype=np.uint8)
    cv2.putText(frame, "Test Frame", (100, 200), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
    fps = 0 # 帧率
    center = (320, 240) #框中心
    number = 1 # 目标数量
    return frame,fps,center,number


if __name__ == "__main__":
    import numpy as np

    # ✅ 方式一：使用相机
    # app = VideoApp(use_camera=True)

    # ✅ 方式二：使用自定义图像源（例如 SLAM、检测器输出帧）
    app = VideoApp(use_camera=True, frame_provider=None,track_handler=None,exit_handler=None)

    app.loop()
