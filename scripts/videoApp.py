import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2
import time

class VideoApp:
    def __init__(self, use_camera=True, frame_provider=None,track_handler=None,exit_handler=None):
        self.frame = None
        self.fps_out = 0
        self.center = (0,0)
        self.number = 0

        self.root = tk.Tk()

        self.root.title("OpenCV Video on Canvas")
        # self.root.resizable(0, 0)
        self.track_handler = track_handler
        self.exit_handler = exit_handler

        # 居中窗口
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.w ,self.h = 640, 480
        win_w, win_h = self.w+20, self.h+20
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2
        self.root.attributes('-alpha', 1)
        self.root.configure(bg='#4B5CC4')
        # self.root.overrideredirect(True)
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.root.resizable(True, True)
        self.root.minsize(640, 480)
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

        self.btn_track = ttk.Button(btn_frame, text="跟随", command=self._track_handle)
        self.btn_track.pack(side=tk.LEFT, padx=0.6)

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

    def _track_handle(self):
        if self.track_handler:
            self.track_handler()
        else:
            print("ui初始化失败！")
            self.quit_all()

    def quit_all(self):

        self.root.quit()
        self.root.destroy()
        if self.exit_handler:
            self.exit_handler()

    # 外部调用函数传递图像与信息
    def set_frame(self,frame=None,fps_out=0,center=(0,0),number=0):
        self.frame = frame
        self.fps_out = fps_out
        self.center = center
        self.number = number

    def get_frame(self,frame=None):
        # 1.直接从相机获取
        if self.use_camera:
            ret, frame = self.cap.read()
            if not ret:
                return None,0,0,0
            return frame,0,0,0
        else:
            # 2.使用frame_provider获取
            if self.frame_provider:
                return self.frame_provider()
            #
            else:
                return self.frame,self.fps_out,self.center,self.number

    def update_frame(self):
        frame,fps_out,center,number= self.get_frame()
        if frame is not None:
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
            self.prev_time = now
            self.data_label.config(text=f"FPSOUT: {fps_out}    |    FPS: {fps}    |    CENTER: {center}    |    QRNumber: {number}")
        else:
            self.data_label.config(text="等待图像...")

        if self.use_camera:
            self.root.after(10, self.update_frame)

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
