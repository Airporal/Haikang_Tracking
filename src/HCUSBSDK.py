'''
    定义SDK的结构体和回调函数

'''
import ctypes as sdk

import os
import platform
import re
from ctypes import *
from enum import Enum


def system_get_platform_info():
    sys_platform = platform.system().lower().strip()
    python_bit = platform.architecture()[0]
    python_bit_num = re.findall('(\d+)\w*', python_bit)[0]
    return sys_platform, python_bit_num


sys_platform, python_bit_num = system_get_platform_info()
system_type = sys_platform + python_bit_num

if sys_platform == 'linux':
    load_library = cdll.LoadLibrary
    fun_ctype = CFUNCTYPE
elif sys_platform == 'windows':
    load_library = windll.LoadLibrary
    fun_ctype = WINFUNCTYPE
else:
    print("************不支持的平台**************")
    exit(0)

current_dir = os.path.dirname(os.path.abspath(__file__))
current_dir = os.path.dirname(current_dir)
target_dir = os.path.abspath(os.path.join(current_dir))

print("------target_dir", target_dir)
usbsdkdllpath_dict = {'windows64': target_dir + '\\lib\\' + 'HCUSBSDK.dll',
                      'windows32': target_dir + '\\lib\\' + 'HCUSBSDK.dll',
                      'linux64': target_dir + '/lib/libHCUSBSDK.so',
                      'linux32': target_dir + '/lib/libHCUSBSDK.so'}
usbsdkdllpath = usbsdkdllpath_dict[system_type]

C_LLONG_DICT = {'windows64': c_longlong, 'windows32': c_long, 'linux32': c_long, 'linux64': c_long}
C_LONG_DICT = {'windows64': c_long, 'windows32': c_long, 'linux32': c_int, 'linux64': c_int}
C_LDWORD_DICT = {'windows64': c_longlong, 'windows32': c_ulong, 'linux32': c_long, 'linux64': c_long}
C_DWORD_DICT = {'windows64': c_ulong, 'windows32': c_ulong, 'linux32': c_uint, 'linux64': c_uint}
C_HWND_DICT = {'windows64': c_void_p, 'windows32': c_void_p, 'linux32': c_uint, 'linux64': c_uint}

C_LLONG = C_LLONG_DICT[system_type]
C_LONG = C_LONG_DICT[system_type]
C_LDWORD = C_LDWORD_DICT[system_type]
C_DWORD = C_DWORD_DICT[system_type]
# C_BOOL = c_int
# C_UINT = c_uint
# C_BYTE = c_ubyte
# C_ENUM = c_int

C_HWND = C_HWND_DICT[system_type]
C_WORD = c_ushort
C_USHORT = c_ushort
C_SHORT = c_short
# C_LONG = c_int
C_BYTE = c_ubyte
C_UINT = c_uint
C_LPVOID = c_void_p
C_HANDLE = c_void_p
C_LPDWORD = POINTER(c_uint)
C_UINT64 = c_ulonglong
C_INT64 = c_longlong
C_BOOL = c_int

MAX_MANUFACTURE_LEN = 32

MAX_DEVICE_NAME_LEN = 32
MAX_SERIAL_NUM_LEN = 48
MAX_PATH_LEN = 260
MAX_USB_DEV_LEN = 64
ERR_LEVEL = 1
DBG_LEVEL = 2
INF_LEVEL = 3
MAX_USERNAME_NAME = 32
MAX_PASSWORD_LEN = 16
INVALID_USER_ID = -1
USB_ERROR_BASE = 0
USB_SUCCESS = (USB_ERROR_BASE + 0)
USB_ERROR_INACTIVED = USB_ERROR_BASE + 70
USB_SDK_GET_ACTIVATE_CARD = 0x0104
USB_SDK_GET_CERTIFICATE_INFO = 1000
MAX_USERNAME_LEN = 32


USB_STREAM_UNKNOW = 0
USB_STREAM_PCM = 1
USB_STREAM_MJPEG = 101
USB_STREAM_YUV = 102
USB_STREAM_H264 = 103

USB_STREAM_PS_H264 = 201
USB_STREAM_PS_MJPEG = 202
# 命令码
dwCommand = {
    'USB_GET_SYSTEM_DEVICE_INFO': 2011,
    'USB_CAMERA_BASE': 3000,
    'USB_GET_VIDEO_CAP': 3001,
    'USB_GET_VIDEO_PARAM': 3003,
    'USB_SET_VIDEO_PARAM': 3004,
    'USB_GET_LIVEDETECT': 3013,
    'USB_GET_VIDEO_PROPERTY_CAP':3014,
    'USB_SET_SRC_STREAM_TYPE': 3007,
    'USB_GET_VIDEO_SHARPNESS': 3023,
    'USB_SET_VIDEO_SHARPNESS': 3024,
    'USB_GET_VIDEO_PAN': 3037,
    'USB_SET_VIDEO_PAN': 3038,
    'USB_GET_VIDEO_TILT': 3039,
    'USB_SET_VIDEO_TILT': 3040,
    'USB_GET_VIDEO_ROLL':3041,
    'USB_SET_VIDEO_ROLL':3042,
    'USB_GET_VIDEO_FOCUS':3049,
    'USB_SET_VIDEO_FOCUS':3050,
    'USB_GET_IMAGE_FOCUS':3128,
    'USB_CTRL_PTZ_BASIC_CONTROL':3135
}

# 枚举定义
# 设置SDK初始化参数类型枚举
class USB_LOCAL_CFG_TYPE(Enum):
    ENUM_LOCAL_CFG_TYPE_LOAD_PATH = 0  # (USB_Init前调用)加载动态库路径配置，对应结构体USB_LOCAL_LOAD_PATH
    ENUM_LOCAL_CFG_TYPE_GUID = 1  # (USB_Init后调用)设置GUID配置，对应结构体USB_LOCAL_GUID结构体在设置扩展ID的需求中定义
    ENUM_LOCAL_CFG_TYPE_FONT_PATH = 2  # 设置字体文件路径，只支持Linux
    ENUM_LOCAL_CFG_TYPE_FACE_DETECT = 3  # (USB_Init前调用)创建人脸检测资源（Linux下使用, win和android不支持）


# 设置动态库路径需要加文件名
class USB_DLL_TYPE(Enum):
    ENUM_DLL_SSL_PATH = 1  # 设置OpenSSL的ssleay32.dll / libssl.so / libssl.dylib所在路径
    ENUM_DLL_CRYPTO_PATH = 2  # 设置OpenSSL的libeay32.dll / libcrypto.so / libcrypto.dylib所在路径
    ENUM_DLL_SYSTEMTRANSFORM_PATH = 3  # 设置转封装库路径
    ENUM_DLL_LIBUSB_PATH = 4  # 设置LIBUSB库路径
    ENUM_DLL_PLAYCTRL_PATH = 5  # 设置播放库路径
    ENUM_DLL_FORMATCONVERSION_PATH = 6  # 设置转码库路径
    ENUM_DLL_LIBUVC_PATH = 8


# 设备信息结构体
class USB_DEVICE_INFO(Structure):
    _fields_ = [
        ("dwSize", C_DWORD),  # 结构体大小
        ("dwIndex", C_DWORD),  # 设备索引
        ("dwVID", C_DWORD),  # 设备VID
        ("dwPID", C_DWORD),  # 设备PID
        ("szManufacturer", C_BYTE * 32),  # 制造商（来自描述符）
        ("szDeviceName", C_BYTE * 32),  # 设备名称（来自描述符）
        ("szSerialNumber", C_BYTE * 48),  # 设备序列号（来自描述符）
        ("byHaveAudio", C_BYTE),  # 是否具有音频
        ("iColorType", C_BYTE),  # 1.RGB路，2.IR路
        ("szDevicePath", C_BYTE * MAX_PATH_LEN),  # 设备路径
        ("byDeviceType", C_BYTE),  # 设备类型
        ("dwBCD", C_DWORD),  # 设备软件版本号
        ("byRes", C_BYTE * 249),  # 保留字节
    ]  # 保留，置为0


LPUSB_DEVICE_INFO = POINTER(USB_DEVICE_INFO)


class OUT_USB_DEVICE_INFO(Structure):
    _fields_ = [
        ("struDeviceArr", POINTER(USB_DEVICE_INFO)),  # 使用指针来存储数组
    ]
    # 列表用以下方式初始化
    def __init__(self, devCount):
        super().__init__()
        self.struDeviceArr = (USB_DEVICE_INFO * devCount)()  # 创建一个包含 devCount 个 USB_DEVICE_INFO 的数组
        for i in range(devCount):
            self.struDeviceArr[i] = USB_DEVICE_INFO()  # 初始化每个元素


# 用户登录信息结构体
class USB_USER_LOGIN_INFO(Structure):
    _fields_ = [
        ('dwSize', C_DWORD),  # 结构体大小
        ('dwTimeout', C_DWORD),  # 登录超时时间（单位：毫秒）
        ('dwDevIndex', C_DWORD),  # 设备下标
        ('dwVID', C_DWORD),  # 设备VID
        ('dwPID', C_DWORD),  # 设备PID
        ('szUserName', C_BYTE * 32),  # 用户名
        ('szPassword', C_BYTE * 16),  # 密码
        ('szSerialNumber', C_BYTE * 48),  # 设备序列号
        ('byLoginMode', C_BYTE),  # 登录模式，0-认证登陆 1-默认账号登陆（不关心用户名密码）（权限不同，部分功能需认证登陆才支持）
        ('byRes2', C_BYTE * 3),  # 保留字节
        ('dwFd', C_DWORD),  # 设备描述符fd(android下没有root权限登录时使用)
        ('byRes', C_BYTE * 248),  # 保留字节
    ]


LPUSB_USER_LOGIN_INFO = POINTER(USB_USER_LOGIN_INFO)

class USB_PTZ_BASIC_CTRL_PARAM(Structure):
    _fields_ = [
        ('dwSize', C_DWORD),  # 结构体大小
        ('byPtzDirection', C_BYTE),  # 1：上，2：下，3：左，4：右，5：放大，6：缩小，7：聚集+，8：聚焦-
        ('byPtzStatus', C_BYTE),  # 0：停止，1：开始
        ('byRes', C_BYTE * 248),  # 保留字节
    ]

# 设备登录结果结构体
class USB_DEVICE_REG_RES(Structure):
    _fields_ = [
        ('dwSize', C_DWORD),  # 结构体大小
        ('szDeviceName', C_BYTE * 32),  # 设备名称
        ('szSerialNumber', C_BYTE * 48),  # 设备序列号
        ('dwSoftwareVersion', C_DWORD),  # 软件版本号
        ('wYear', C_WORD),  # 年
        ('byMonth', C_BYTE),  # 月
        ('byDay', C_BYTE),  # 日
        ('byRetryLoginTimes', C_BYTE),  # 剩余可尝试登录的次数
        ('byRes1', C_BYTE * 3),  # 保留字节
        ('dwSurplusLockTime', C_DWORD),  # 剩余时间，单位秒
        ('byRes', C_BYTE * 256),  # 保留字节
    ]


# 配置输入信息结构体
class USB_CONFIG_INPUT_INFO(Structure):
    _fields_ = [
        ('lpCondBuffer', c_void_p),  # 指向条件缓冲区
        ('dwCondBufferSize', C_DWORD),  # 条件缓冲区大小
        ('lpInBuffer', c_void_p),  # 指向输出缓冲区
        ('dwInBufferSize', C_DWORD),  # 输入缓冲区大小
        ('byRes', C_BYTE * 48),  # 保留字节
    ]
POINTER_USB_CONFIG_INPUT_INFO = POINTER(USB_CONFIG_INPUT_INFO)
# 配置输出信息结构体
class USB_CONFIG_OUTPUT_INFO(Structure):
    _fields_ = [
        ('lpOutBuffer', c_void_p),  # 指向输出缓冲区
        ('dwOutBufferSize', C_DWORD),  # 输出缓冲区大小
        ('byRes', C_BYTE * 56),  # 保留字节
    ]
POINTER_USB_CONFIG_OUTPUT_INFO = POINTER(USB_CONFIG_OUTPUT_INFO)

# 预览参数结构体
class USB_PREVIEW_PARAM(Structure):
    _fields_ = [
        ('dwSize', C_DWORD),  # 结构体大小
        ('dwStreamType', C_DWORD),  # 码流类型
        ('dwChannel', C_DWORD),  # 码流类型
        ('hWindow', C_HWND),  # 窗口句柄
        ('bUseAudio', C_BYTE),  # 是否预览音频
        ('bYUVCallback', C_BYTE),  # 是否开启YUV回调
        ('byRes', C_BYTE * 126),  # 保留字节
    ]


# 抓拍图片参数结构体
class USB_CAPTURE_PARAM(Structure):
    _fields_ = [
        ('dwSize', C_DWORD),  # sizeof(USB_CAMERA_CAPTURE_PARAM)
        ('dwType', C_DWORD),  # 抓图方式：0-内部写文件，1-返回图片数据
        ('pBuf', POINTER(C_BYTE)),  # 数据缓冲区
        ('dwBufSize', C_DWORD),  # 数据缓冲区大小
        ('dwDataLen', C_DWORD),  # 数据缓冲区中有效数据长度(即图片大小)
        ('szFilePath', C_BYTE * 256),  # 图片存储路径
        ('byRes', C_BYTE * 32),  # 保留字节
    ]


# 相机视频参数结构体
class USB_VIDEO_PARAM(Structure):
    _fields_ = [
        ('dwVideoFormat', C_DWORD),  # 视频码流格式
        ('dwWidth', C_DWORD),  # 分辨率宽
        ('dwHeight', C_DWORD),  # 分辨率高
        ('dwFramerate', C_DWORD),  # 帧率
        ('dwBitrate', C_DWORD),  # 比特率
        ('dwParamType', C_DWORD),  # 图像参数类型
        ('dwValue', C_DWORD),  # 图像参数值
        ('byRes', C_BYTE * 128),  # 保留字节
    ]

class USB_VIDEO_PROPERTY(Structure):
    _fields_ = [
        ('dwValue', c_long),
        ('byFlag', C_BYTE),
        ('byRes', C_BYTE * 31),  # 保留字节
    ]
class USB_PROPERTY(Structure):
    _fields_ = [
        ('IMin',c_long), # 最小值
        ('IMax',c_long), # 最大值
        ('IStep',c_long), # 步长
        ('IDef',c_long), # 默认值
        ('byEnabled',C_BYTE), # 是否支持，0-不支持，1-支持，2-手动，3-自动
        ('byRes',C_BYTE * 7),

    ]
class USB_VIDEO_PROPERTY_CAP(Structure):
    _fields_ = [
        ('struBrightness', USB_PROPERTY),  # 亮度 1
        ('struContrast', USB_PROPERTY), # 对比度 1
        ('struHue', USB_PROPERTY),# 色调 2
        ('struSaturation', USB_PROPERTY),# 饱和度 2
        ('struSharpness', USB_PROPERTY), # 锐度 2
        ('struGamma', USB_PROPERTY), # 伽马 2
        ('struColorEnable', USB_PROPERTY), # 颜色增益 2
        ('struWhiteBalance', USB_PROPERTY), # 白平衡 3
        ('struBacklightCompensation', USB_PROPERTY), # 背光补偿 0
        ('struGain', USB_PROPERTY), # 增益 2
        ('struPowerLineFrequency', USB_PROPERTY), # 电平频率 0
        ('struPan', USB_PROPERTY), # 左右摆动 0
        ('struTilt', USB_PROPERTY), # 上下摆动 0
        ('struRoll', USB_PROPERTY), # 左右翻滚 2
        ('struZoom', USB_PROPERTY), # 缩放 2
        ('struExposure', USB_PROPERTY), # 曝光 0
        ('struIris', USB_PROPERTY), # 光圈 0
        ('struFocus', USB_PROPERTY), # 焦距 3
        ('struLowBrightnessCompensation', USB_PROPERTY), # 低亮度补偿
        ('byRes', C_BYTE * 128),  # 保留字节
    ]

# 关于原始码流配置参数的结构体
class USB_SRC_STREAM_CFG(Structure):
    _fields_ = [
        ('dwStreamType', C_DWORD),  # 原始码流类型(MJPEG/H264/YUV)
        ('bUseAudio', C_BYTE),  # 是否使用音频 0-不使用，1-使用
        ('byRes', C_BYTE * 4),  # 保留字节
    ]


# 人脸小图参数结构体
class USB_SUBFACE_PIC(Structure):
    _fields_ = [
        ('dwWidth', C_DWORD),  # 小图宽度
        ('dwHeight', C_DWORD),  # 小图高度
        ('pSubFacePic', POINTER(C_BYTE)),  # 人脸小图
        ('dwSubFacePicLen', C_DWORD),  # 人脸小图大小
        ('byRes', C_BYTE * 16),  # 保留字节
    ]


# 人脸图片质量结构体
class USB_FACE_QUALITY(Structure):
    _fields_ = [
        ('fEyeDistance', c_float),  # 两眼间距,真实像素值
        ('fGrayMean', c_float),  # 灰阶均值，范围0~255
        ('fGrayVariance', c_float),  # 灰阶均方差，范围0~128
        ('fClearityScore', c_float),  # 清晰度评分，范围0~1
        ('fPosePitch', c_float),  # 平面外上下俯仰角，人脸朝上为正，范围-90~90
        ('fPoseYaw', c_float),  # 平面外左右偏转角，人脸朝左为正，范围-90~90
        ('fPoseRoll', c_float),  # 平面内旋转角，人脸顺时针旋转为正，范围-90~90
        ('fPoseConfidence', c_float),  # 姿态(pose_pitch、pose_yaw、pose_roll)置信度，范围0~1
        ('fFrontalScore', c_float),  # 正面程度评分，范围0~1
        ('fVisibleScore', c_float),  # 可见性评分（即不遮挡），范围0~1，0表示完全遮挡，1表示完全不遮挡
        ('fFaceScore', c_float),  # 人脸评分，范围0~1
        ('byRes', C_BYTE * 128),  # 保留字节
    ]


# 单个人脸图片参数结构体。最多支持 64 组人脸图片参数。
class USB_FACE_PARAM(Structure):
    _fields_ = [
        ('struFaceQualityList', USB_FACE_QUALITY),
        ('struSubFacePic', USB_SUBFACE_PIC),
        ('byRes', C_BYTE * 16),  # 保留字节
    ]


# 人脸底图参数结构体
class USB_MEDIA_DATA(Structure):
    _fields_ = [
        ('dwWidth', C_DWORD),  # 宽度
        ('dwHeight', C_DWORD),  # 高度
        ('dwFrameRate', C_DWORD),  # 帧率
        ('dwTimeStamp', C_DWORD),  # 时间戳
        ('dwFrameNum', C_DWORD),  # 帧号
        ('dwLen', C_DWORD),  # 背景图数据长度
        ('pBuffer', POINTER(C_BYTE)),  # 背景图缓存
        ('dwSysTime', C_DWORD),  # 系统时间戳
        ('byRes', C_BYTE * 128),  # 保留字节
    ]


# 目标识别结果结构体
class USB_FD_RESULT_PARAM(Structure):
    _fields_ = [
        ('dwFaceTotalNum', C_DWORD),  # 人脸总的个数
        ('struMediaData', USB_MEDIA_DATA),
        ('struFaceParam', USB_FACE_PARAM * 64),  # 单个人脸参数
        ('byRes', C_BYTE * 32),  # 保留字节
    ]


LPUSB_FD_RESULT_PARAM = POINTER(USB_FD_RESULT_PARAM)

# 异步登录回调函数
FDExtenResultCallBack = fun_ctype(None, C_LONG, LPUSB_FD_RESULT_PARAM, c_void_p)


# 目标识别结果结构体
class USB_FACE_DETECT_PARAM(Structure):
    _fields_ = [
        ('fnFDExtenResultCallBack', FDExtenResultCallBack),  # 人脸属性检测结果数据回调
        ('pUser', c_void_p),
        ('bySnapMode', C_BYTE),  # 抓图模式  0:自动抓图 1:手动抓图     【预留，不支持】
        ('byRes', C_BYTE * 503),  # 保留字节
    ]

class USB_LOCAL_LOAD_PATH(Structure):
    _fields_ = [
        ('emType', C_DWORD),  # 加载库的类型
        ('byLoadPath', C_BYTE * 256),
        ('byRes', C_BYTE * 128),  # 保留字节
    ]

class USB_VIDEO_CAPACITY(Structure):
    _fields_ = [
        ('nIndex', c_byte),  # 索引
        ('nType', c_byte),  # 码流类型
        ('dwWidth', C_DWORD),  # 水平分辨率
        ('dwHeight', C_DWORD),  # 垂直分辨率
        ('IListSizes', C_LONG), # 支持帧率类型数量
        ('IFrameRates', C_LONG * 50),  # 保留字节
    ]
class USB_FR_LIVE_INFO(Structure):
    _fields_ = [
        ('nLiveStatus', C_DWORD),  # 结构体大小
        ('fLiveConfidence', c_float),
        ('reserved', C_BYTE * 16)
    ]
class USB_FACE_ATTR_CLS(Structure):
    _fields_ = [
        ('nValue', C_DWORD),  # 人脸个数
        ('fConf', c_float),  # 人脸质量
    ]

class USB_FACE_ATTR_OUT(Structure):
    _fields_ = [
        ('stAge', USB_FACE_ATTR_CLS),  # 人脸个数
        ('stGender', USB_FACE_ATTR_CLS),  # 人脸质量
        ('stGlass', USB_FACE_ATTR_CLS),  # 人脸小图
        ('stExpress', USB_FACE_ATTR_CLS),  # 人脸个数
        ('stMask', USB_FACE_ATTR_CLS),  # 人脸质量
        ('stHat', USB_FACE_ATTR_CLS),  # 人脸小图
        ('stReserved', C_BYTE * 64),  # 保留字节
    ]
class USB_TARGET_LIVE_INFO(Structure):
    _fields_ = [
        ('strLiveInfo', USB_FR_LIVE_INFO),  # 活体检测结果
        ('strFaceAttr', USB_FACE_ATTR_OUT)
    ]

class USB_FR_LIVE_PARAM(Structure):
    _fields_ = [
        ('LiveNum', C_DWORD),  # 结构体大小
        ('stTargetLiveOut', USB_TARGET_LIVE_INFO*64),  # 码流类型
    ]

class USB_LIVE_COND_INFO(Structure):
    _fields_ = [
        ('dwWidth', c_uint),
        ('dwHeight', c_uint),
        ('pRGBBuf', POINTER(c_ubyte)),
        ('pRGBBufLen', c_uint ),
        ('pIRBuf',POINTER(c_ubyte)),
        ('pIRBufLen',c_uint)
    ]

