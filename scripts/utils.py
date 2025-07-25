import os
import platform
import re
import numpy as np
from HCNetSDK import *
from filterpy.kalman import KalmanFilter
import math
import cv2
from PIL import Image
import io
import time

def system_get_platform_info():
    sys_platform = platform.system().lower().strip()
    python_bit = platform.architecture()[0]
    python_bit_num = re.findall('(\d+)\w*', python_bit)[0]
    system_type = sys_platform + python_bit_num
    return sys_platform, system_type # windows windows64 str类型
def is_windows():
    sys_platform, system_type = system_get_platform_info()
    if sys_platform == 'windows':
        print('windows')
        return True
    else:
        return False

def set_path(WINDOWS_FLAG):
    if WINDOWS_FLAG:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(current_dir)
        basePath = project_dir.encode('gbk')
        libPath = basePath + b'\core'
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(current_dir)
        basePath = project_dir.encode('utf-8')
        libPath = basePath + b'\core'
    logPath = basePath + b'/SdkLog_Python/'
    return basePath, libPath, logPath


def calculate_dynamic_sleep(diff_x, diff_y, max_diff, min_sleep, max_sleep):
    """
    估计动态睡眠时间
    :param diff_x:
    :param diff_y:
    :param max_diff:
    :param min_sleep:
    :param max_sleep:
    :return: sleep_time
    """
    # 计算总的距离
    distance = math.sqrt(diff_x ** 2 + diff_y ** 2)
    # 归一化距离并映射到sleep时间
    sleep_time = min(distance / 400 * 0.1, max_sleep)
    return sleep_time
def draw_trajectory_on_image(image, history_centers, predicted_position):
    # 历史点颜色和尺寸
    history_color = (255, 0, 0)  # 蓝色
    history_size = 3

    # 预测点颜色和尺寸
    predicted_color = (0, 0, 255)  # 红色
    predicted_size = 5

    # 绘制历史轨迹点
    for center in history_centers:
        center_int = (int(center[0]), int(center[1]))
        cv2.circle(image, center_int, history_size, history_color, -1)

    # 绘制轨迹线
    for i in range(1, len(history_centers)):
        cv2.line(image, history_centers[i - 1], history_centers[i], history_color, 2)

    # 绘制预测点
    if predicted_position is not None:
        predicted_position=(int(predicted_position[0]), int(predicted_position[1]))
        cv2.circle(image, predicted_position, predicted_size, predicted_color, -1)
        if history_centers:
            # 从最后一个历史点连线到预测点
            cv2.line(image, history_centers[-1], predicted_position, predicted_color, 2)

    return image

def predict_next_position_kalman(history_centers, kf):
    if not history_centers:
        return None

    last_center = history_centers[-1]
    kf.predict()
    kf.update(last_center)

    predicted = kf.x[:2]  # 预测的位置
    return int(predicted[0]), int(predicted[1])



def initialize_kalman_filter():
    kf = KalmanFilter(dim_x=4, dim_z=2)
    kf.x = np.array([0., 0., 0., 0.])  # 初始状态 (位置和速度)
    kf.F = np.array([[1, 0, 1, 0],    # 状态转移矩阵
                     [0, 1, 0, 1],
                     [0, 0, 1, 0],
                     [0, 0, 0, 1]])
    kf.H = np.array([[1, 0, 0, 0],    # 测量函数
                     [0, 1, 0, 0]])
    kf.P *= 1000.                    # 协方差矩阵
    kf.R = np.array([[1, 0],         # 测量噪声
                     [0, 1]])
    kf.Q = np.eye(kf.dim_x) * 0.1    # 过程噪声

    return kf

def get_frame_jpeg_auto(Playctrldll, port, init_buf_size=16 * 1024 * 1024):
    buf_size = init_buf_size
    for _ in range(5):  # 最多尝试5次
        buf = ctypes.create_string_buffer(buf_size)
        jpeg_size = ctypes.c_uint32()
        ok = Playctrldll.PlayM4_GetJPEG(port, buf, buf_size, ctypes.byref(jpeg_size))
        if ok:
            data = buf.raw[:jpeg_size.value]

            # 修剪数据：找 0xFFD9 结束标志，避免 PIL 报错
            eoi_marker = b'\xff\xd9'
            eoi_index = data.find(eoi_marker)
            if eoi_index != -1 and eoi_index + 2 < len(data):
                data = data[:eoi_index + 2]

            try:
                image = Image.open(io.BytesIO(data)).convert("RGB")  # 转为 RGB
                return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)  # 转回 OpenCV 格式
            except Exception as e:
                print(f"❌ PIL 解码失败: {e}")
                return None

        err = Playctrldll.PlayM4_GetLastError(port)
        if err == 34:  # 缓冲区太小
            print(f"⚠️ GetJPEG 缓冲区太小，扩大至 {buf_size * 2 // 1024} KB")
            buf_size *= 2
        else:
            print(f"❌ GetJPEG failed, 错误码: {err}")
            time.sleep(0.1)
            break

    return None

def get_frame_jpeg_cv(Playctrldll, port, buf_size=16 * 1024 * 1024):
    buf = ctypes.create_string_buffer(buf_size)
    jpeg_size = ctypes.c_uint32()

    ok = Playctrldll.PlayM4_GetJPEG(port, buf, buf_size, ctypes.byref(jpeg_size))
    if not ok:
        err = Playctrldll.PlayM4_GetLastError(port)
        print(f"GetJPEG failed, error code: {err}")
        return None

    # 从缓冲区获取 JPEG 数据
    data = bytearray(buf.raw[:jpeg_size.value])

    # 修剪数据：寻找 JPEG 结束标记 0xFFD9，避免多余字节导致 OpenCV 警告或解码失败
    eoi_marker = b'\xff\xd9'
    eoi_index = data.find(eoi_marker)

    if eoi_index != -1 and eoi_index + 2 < len(data):
        data = data[:eoi_index + 2]

    # 尝试用 OpenCV 解码
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)

    if img is None:
        print("⚠️ OpenCV 解码失败，图像为空")
        return None

    return img

def get_frame_bmp(Playctrldll,port, init_buf_size=32 * 1024 * 1024):
    buf_size = init_buf_size
    for _ in range(3):
        buf = ctypes.create_string_buffer(buf_size)
        bmp_size = ctypes.c_uint32()

        ok =Playctrldll.PlayM4_GetBMP(port, buf, buf_size, ctypes.byref(bmp_size))
        if ok:
            try:
                bmp_data = buf.raw[:bmp_size.value]
                image = Image.open(io.BytesIO(bmp_data)).convert("RGB")
                return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            except Exception as e:
                print(f"❌ BMP 解码失败: {e}")
                return None
        else:
            err = Playctrldll.PlayM4_GetLastError(port)
            if err == 34:
                print(f"⚠️ BMP缓冲区太小，扩大至 {buf_size * 2 // 1024} KB")
                buf_size *= 2
            else:
                print(f"❌ GetBMP failed, 错误码: {err}")
                time.sleep(0.1)
                break
    return None
def get_frame_jpeg_auto(Playctrldll, port, init_buf_size=16 * 1024 * 1024):
    buf_size = init_buf_size
    for _ in range(5):  # 最多尝试5次
        buf = ctypes.create_string_buffer(buf_size)
        jpeg_size = ctypes.c_uint32()
        ok = Playctrldll.PlayM4_GetJPEG(port, buf, buf_size, ctypes.byref(jpeg_size))
        if ok:
            data = buf.raw[:jpeg_size.value]

            # 修剪数据：找 0xFFD9 结束标志，避免 PIL 报错
            eoi_marker = b'\xff\xd9'
            eoi_index = data.find(eoi_marker)
            if eoi_index != -1 and eoi_index + 2 < len(data):
                data = data[:eoi_index + 2]

            try:
                image = Image.open(io.BytesIO(data)).convert("RGB")  # 转为 RGB
                return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)  # 转回 OpenCV 格式
            except Exception as e:
                print(f"❌ PIL 解码失败: {e}")
                return None

        err = Playctrldll.PlayM4_GetLastError(port)
        if err == 34:  # 缓冲区太小
            print(f"⚠️ GetJPEG 缓冲区太小，扩大至 {buf_size * 2 // 1024} KB")
            buf_size *= 2
        else:
            print(f"❌ GetJPEG failed, 错误码: {err}")
            time.sleep(0.1)
            break

    return None

def get_frame_jpeg_cv(Playctrldll, port, buf_size=16 * 1024 * 1024):
    buf = ctypes.create_string_buffer(buf_size)
    jpeg_size = ctypes.c_uint32()

    ok = Playctrldll.PlayM4_GetJPEG(port, buf, buf_size, ctypes.byref(jpeg_size))
    if not ok:
        err = Playctrldll.PlayM4_GetLastError(port)
        print(f"GetJPEG failed, error code: {err}")
        return None

    # 从缓冲区获取 JPEG 数据
    data = bytearray(buf.raw[:jpeg_size.value])

    # 修剪数据：寻找 JPEG 结束标记 0xFFD9，避免多余字节导致 OpenCV 警告或解码失败
    eoi_marker = b'\xff\xd9'
    eoi_index = data.find(eoi_marker)

    if eoi_index != -1 and eoi_index + 2 < len(data):
        data = data[:eoi_index + 2]

    # 尝试用 OpenCV 解码
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)

    if img is None:
        print("⚠️ OpenCV 解码失败，图像为空")
        return None

    return img

def get_frame_bmp(Playctrldll,port, init_buf_size=32 * 1024 * 1024):
    buf_size = init_buf_size
    for _ in range(3):
        buf = ctypes.create_string_buffer(buf_size)
        bmp_size = ctypes.c_uint32()

        ok =Playctrldll.PlayM4_GetBMP(port, buf, buf_size, ctypes.byref(bmp_size))
        if ok:
            try:
                bmp_data = buf.raw[:bmp_size.value]
                image = Image.open(io.BytesIO(bmp_data)).convert("RGB")
                return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            except Exception as e:
                print(f"❌ BMP 解码失败: {e}")
                return None
        else:
            err = Playctrldll.PlayM4_GetLastError(port)
            if err == 34:
                print(f"⚠️ BMP缓冲区太小，扩大至 {buf_size * 2 // 1024} KB")
                buf_size *= 2
            else:
                print(f"❌ GetBMP failed, 错误码: {err}")
                time.sleep(0.1)
                break
    return None
frame_mode_set = {
"kcf": lambda: cv2.TrackerKCF.create(),
    0:lambda: get_frame_bmp(),
    1:lambda:get_frame_jpeg_cv(),
    2:lambda:get_frame_jpeg_auto(),
}
if __name__ == '__main__':
    sys_platform, python_bit_num = system_get_platform_info()
    system_type = sys_platform + python_bit_num
    print(sys_platform)