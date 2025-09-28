from ctypes import *
BYTE = c_ubyte
WORD = c_ushort
DWORD = c_uint32
INT = c_int32

sceneMode = {0:"室外场景",
             1:"室内场景",
             2:"默认场景",
             3:"弱光场景"}

class NET_DVR_VIDEOEFFECT(Structure):
    _fields_ = [
        ("byBrightnessLevel", c_ubyte),
        ("byContrastLevel", c_ubyte),
        ("bySharpnessLevel", c_ubyte),
        ("bySaturationLevel", c_ubyte),
        ("byHueLevel", c_ubyte),
        ("byEnableFunc", c_ubyte),
        ("byLightInhibitLevel", c_ubyte),
        ("byGrayLevel", c_ubyte),
    ]

class NET_DVR_GAIN(Structure):
    _fields_ = [
        ("byGainLevel", c_ubyte),
        ("byGainUserSet", c_ubyte),
        ("byRes", c_ubyte * 2),
        ("dwMaxGainValue", c_uint32),
    ]

class NET_DVR_WHITEBALANCE(Structure):
    _fields_ = [
        ("byWhiteBalanceMode", c_ubyte),
        ("byWhiteBalanceModeRGain", c_ubyte),
        ("byWhiteBalanceModeBGain", c_ubyte),
        ("byRes", c_ubyte * 5),
    ]

class NET_DVR_EXPOSURE(Structure):
    _fields_ = [
        ("byExposureMode", c_ubyte),
        ("byAutoApertureLevel", c_ubyte),
        ("byRes", c_ubyte * 2),
        ("dwVideoExposureSet", c_uint32),
        ("dwExposureUserSet", c_uint32),
        ("dwRes", c_uint32),
    ]

class NET_DVR_GAMMACORRECT(Structure):
    _fields_ = [
        ("byGammaCorrectionEnabled", c_ubyte),
        ("byGammaCorrectionLevel", c_ubyte),
        ("byRes", c_ubyte * 6),
    ]

class NET_DVR_WDR(Structure):
    _fields_ = [
        ("byWDREnabled", c_ubyte),
        ("byWDRLevel1", c_ubyte),
        ("byWDRLevel2", c_ubyte),
        ("byWDRContrastLevel", c_ubyte),
        ("byRes", c_ubyte * 16),
    ]

class NET_DVR_DAYNIGHT(Structure):
    _fields_ = [
        ("byDayNightFilterType", c_ubyte),
        ("bySwitchScheduleEnabled", c_ubyte),
        ("byBeginTime", c_ubyte),
        ("byEndTime", c_ubyte),
        ("byDayToNightFilterLevel", c_ubyte),
        ("byNightToDayFilterLevel", c_ubyte),
        ("byDayNightFilterTime", c_ubyte),
        ("byBeginTimeMin", c_ubyte),
        ("byBeginTimeSec", c_ubyte),
        ("byEndTimeMin", c_ubyte),
        ("byEndTimeSec", c_ubyte),
        ("byAlarmTrigState", c_ubyte),
    ]

class NET_DVR_BACKLIGHT(Structure):
    _fields_ = [
        ("byBacklightMode", c_ubyte),
        ("byBacklightLevel", c_ubyte),
        ("byRes1", c_ubyte * 2),
        ("dwPositionX1", c_uint32),
        ("dwPositionY1", c_uint32),
        ("dwPositionX2", c_uint32),
        ("dwPositionY2", c_uint32),
        ("byRes2", c_ubyte * 4),
    ]

class NET_DVR_NOISEREMOVE(Structure):
    _fields_ = [
        ("byDigitalNoiseRemoveEnable", c_ubyte),
        ("byDigitalNoiseRemoveLevel", c_ubyte),
        ("bySpectralLevel", c_ubyte),
        ("byTemporalLevel", c_ubyte),
        ("byDigitalNoiseRemove2DEnable", c_ubyte),
        ("byDigitalNoiseRemove2DLevel", c_ubyte),
        ("byRes", c_ubyte * 2),
    ]

class NET_DVR_CMOSMODECFG(Structure):
    _fields_ = [
        ("byCaptureMod", c_ubyte),
        ("byBrightnessGate", c_ubyte),
        ("byCaptureGain1", c_ubyte),
        ("byCaptureGain2", c_ubyte),
        ("dwCaptureShutterSpeed1", c_uint32),
        ("dwCaptureShutterSpeed2", c_uint32),
        ("byRes", c_ubyte * 4),
    ]

class NET_DVR_DEFOGCFG(Structure):
    _fields_ = [
        ("byMode", c_ubyte),
        ("byLevel", c_ubyte),
        ("byRes", c_ubyte * 6),
    ]

class NET_DVR_ELECTRONICSTABILIZATION(Structure):
    _fields_ = [
        ("byEnable", c_ubyte),
        ("byLevel", c_ubyte),
        ("byRes", c_ubyte * 6),
    ]

class NET_DVR_CORRIDOR_MODE_CCD(Structure):
    _fields_ = [
        ("byEnableCorridorMode", c_ubyte),
        ("byRes", c_ubyte * 11),
    ]

class NET_DVR_SMARTIR_PARAM(Structure):
    _fields_ = [
        ("byMode", c_ubyte),
        ("byIRDistance", c_ubyte),
        ("byShortIRDistance", c_ubyte),
        ("byLongIRDistance", c_ubyte),
    ]

class NET_DVR_PIRIS_PARAM(Structure):
    _fields_ = [
        ("byMode", c_ubyte),
        ("byPIrisAperture", c_ubyte),
        ("byRes", c_ubyte * 6),
    ]

class NET_DVR_LASER_PARAM_CFG(Structure):
    _fields_ = [
        ("byControlMode", c_ubyte),
        ("bySensitivity", c_ubyte),
        ("byTriggerMode", c_ubyte),
        ("byBrightness", c_ubyte),
        ("byAngle", c_ubyte),
        ("byLimitBrightness", c_ubyte),
        ("byEnabled", c_ubyte),
        ("byIllumination", c_ubyte),
        ("byLightAngle", c_ubyte),
        ("byRes", c_ubyte * 7),
    ]

class NET_DVR_FFC_PARAM(Structure):
    _fields_ = [
        ("byMode", c_ubyte),
        ("byRes1", c_ubyte),
        ("wCompensateTime", c_uint16),
        ("byRes2", c_ubyte * 4),
    ]

class NET_DVR_DDE_PARAM(Structure):
    _fields_ = [
        ("byMode", c_ubyte),
        ("byNormalLevel", c_ubyte),
        ("byExpertLevel", c_ubyte),
        ("byRes", c_ubyte * 5),
    ]

class NET_DVR_AGC_PARAM(Structure):
    _fields_ = [
        ("bySceneType", c_ubyte),
        ("byLightLevel", c_ubyte),
        ("byGainLevel", c_ubyte),
        ("byRes", c_ubyte * 5),
    ]
class NET_DVR_TIME_EX(Structure):
    _fields_ = [
        ("wYear", WORD),       # 年（如2025）
        ("byMonth", BYTE),     # 月（1-12）
        ("byDay", BYTE),       # 日（1-31）
        ("byHour", BYTE),      # 时（0-23）
        ("byMinute", BYTE),    # 分（0-59）
        ("bySecond", BYTE),    # 秒（0-59）
        ("byRes", BYTE),       # 保留位
    ]

class NET_DVR_SNAP_CAMERAPARAMCFG(Structure):
    _fields_ = [
        ("byWDRMode", BYTE),
        ("byWDRType", BYTE),
        ("byWDRLevel", BYTE),
        ("byRes1", BYTE),
        ("struStartTime", NET_DVR_TIME_EX),
        ("struEndTime", NET_DVR_TIME_EX),
        ("byDayNightBrightness", BYTE),
        ("byMCEEnabled", BYTE),
        ("byMCELevel", BYTE),
        ("byAutoContrastEnabled", BYTE),
        ("byAutoContrastLevel", BYTE),
        ("byLSEDetailEnabled", BYTE),
        ("byLSEDetailLevel", BYTE),
        ("byLPDEEnabled", BYTE),
        ("byLPDELevel", BYTE),
        ("byRes", BYTE * 35)
    ]

class NET_DVR_OPTICAL_DEHAZE(Structure):
    _fields_ = [
        ("byEnable", c_ubyte),
        ("byRes", c_ubyte * 7),
    ]

class NET_DVR_THERMOMETRY_AGC(Structure):
    _fields_ = [
        ("byMode", c_ubyte),
        ("byRes1", c_ubyte*3),
        ("iHighTemperature", c_int),
        ("iLowTemperature", c_int),
        ("byRes", c_ubyte * 8),
    ]


class NET_DVR_CAMERAPARAMCFG_EX(Structure):
    _fields_ = [
        ("dwSize", DWORD),
        ("struVideoEffect", NET_DVR_VIDEOEFFECT),
        ("struGain", NET_DVR_GAIN),
        ("struWhiteBalance", NET_DVR_WHITEBALANCE),
        ("struExposure", NET_DVR_EXPOSURE),
        ("struGammaCorrect", NET_DVR_GAMMACORRECT),
        ("struWdr", NET_DVR_WDR),
        ("struDayNight", NET_DVR_DAYNIGHT),
        ("struBackLight", NET_DVR_BACKLIGHT),
        ("struNoiseRemove", NET_DVR_NOISEREMOVE),
        ("byPowerLineFrequencyMode", BYTE),
        ("byIrisMode", BYTE),
        ("byMirror", BYTE),
        ("byDigitalZoom", BYTE),
        ("byDeadPixelDetect", BYTE),
        ("byBlackPwl", BYTE),
        ("byEptzGate", BYTE),
        ("byLocalOutputGate", BYTE),
        ("byCoderOutputMode", BYTE),
        ("byLineCoding", BYTE),
        ("byDimmerMode", BYTE),
        ("byPaletteMode", BYTE),
        ("byEnhancedMode", BYTE),
        ("byDynamicContrastEN", BYTE),
        ("byDynamicContrast", BYTE),
        ("byJPEGQuality", BYTE),
        ("struCmosModeCfg", NET_DVR_CMOSMODECFG),
        ("byFilterSwitch", BYTE),
        ("byFocusSpeed", BYTE),
        ("byAutoCompensationInterval", BYTE),
        ("bySceneMode", BYTE),
        ("struDefogCfg", NET_DVR_DEFOGCFG),
        ("struElectronicStabilization", NET_DVR_ELECTRONICSTABILIZATION),
        ("struCorridorMode", NET_DVR_CORRIDOR_MODE_CCD),
        ("byExposureSegmentEnable", BYTE),
        ("byBrightCompensate", BYTE),
        ("byCaptureModeN", BYTE),
        ("byCaptureModeP", BYTE),
        ("struSmartIRParam", NET_DVR_SMARTIR_PARAM),
        ("struPIrisParam", NET_DVR_PIRIS_PARAM),
        ("struLaserParam", NET_DVR_LASER_PARAM_CFG),
        ("struFFCParam", NET_DVR_FFC_PARAM),
        ("struDDEParam", NET_DVR_DDE_PARAM),
        ("struAGCParam", NET_DVR_AGC_PARAM),
        ("byLensDistortionCorrection", BYTE),
        ("byDistortionCorrectionLevel", BYTE),
        ("byCalibrationAccurateLevel", BYTE),
        ("byZoomedInDistantViewLevel", BYTE),
        ("struSnapCCD", NET_DVR_SNAP_CAMERAPARAMCFG),
        ("struOpticalDehaze", NET_DVR_OPTICAL_DEHAZE),
        ("struThermAGC", NET_DVR_THERMOMETRY_AGC),
        ("byFusionMode", BYTE),
        ("byHorizontalFOV", BYTE),
        ("byVerticalFOV", BYTE),
        ("byBrightnessSuddenChangeSuppression", BYTE),
        ("byRes2", BYTE * 156),
    ]
