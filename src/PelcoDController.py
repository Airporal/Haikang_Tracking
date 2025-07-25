import serial
import serial.rs485
import serial.tools.list_ports
import time

class PelcoDController:
    """
        使用RS485控制海康摄像头云台，可以运动但没有反馈
        控制云台水平和俯仰旋转
    """
    def __init__(self, baudrate=9600, timeout=0.1, address=1):
        self.port = self._find_port()
        if not self.port:
            raise RuntimeError("未检测到 CH340 RS‑485 适配器")
        self.ser = serial.Serial(self.port, baudrate=baudrate, timeout=timeout)
        self.ser.rs485_mode = serial.rs485.RS485Settings(
            rts_level_for_tx=True, rts_level_for_rx=False, loopback=False
        )
        self.address = address

    def _find_port(self):
        for p in serial.tools.list_ports.comports():
            if 'CH340' in p.description or (p.vid == 0x1A86 and p.pid == 0x7523):
                return p.device
        return None

    @staticmethod
    def _compute_checksum(pkt: bytes) -> int:
        return sum(pkt[1:6]) % 256

    def send_packet(self, cmd2: int, data1: int = 0, data2: int = 0):
        pkt = bytearray(7)
        pkt[0] = 0xFF
        pkt[1] = self.address
        pkt[2] = 0x00
        pkt[3] = cmd2
        pkt[4] = data1 & 0xFF
        pkt[5] = data2 & 0xFF
        pkt[6] = self._compute_checksum(pkt)
        self.ser.write(pkt)

    def pan_to_angle(self, angle_deg: float):
        """旋转云台到指定绝对角度（单位度）"""
        pos = int(angle_deg * 100)
        if not (0 <= pos <= 35999):
            raise ValueError("Pan angle must be within 0–359.99°")
        high = (pos >> 8) & 0xFF
        low = pos & 0xFF
        self.send_packet(cmd2=0x4B, data1=high, data2=low)
        time.sleep(0.1)  # 建议等待100ms后再发送其他位置命令

    def tilt_to_angle(self, angle_deg: float):
        """设置云台俯仰到绝对角度（单位度）"""
        pos = int(angle_deg * 100)
        if not (0 <= pos <= 35999):
            raise ValueError("Tilt angle must be within 0–359.99°")
        high = (pos >> 8) & 0xFF
        low = pos & 0xFF
        self.send_packet(cmd2=0x4D, data1=high, data2=low)
        time.sleep(0.1)

    def stop(self):
        self.send_packet(cmd2=0x00, data1=0, data2=0)

    def close(self):
        self.ser.close()

if __name__ == '__main__':
    ctrl = PelcoDController(address=1)
    ctrl.pan_to_angle(0)    # 旋转到 90°
    # time.sleep(5)
    # ctrl.tilt_to_angle(30)   # 俯仰至 45°
    ctrl.close()
