import serial
import serial.tools.list_ports
import time
class PelcoDPTZ:
    """
    Pelco-D 协议云台控制类
    仅支持运动控制（上下左右+组合方向），无反馈
    """

    def __init__(self, baudrate=9600, timeout=0.1, address=1):
        self.port = self._find_port()
        if not self.port:
            raise RuntimeError("未检测到 CH340 RS-485 适配器")
        self.ser = serial.Serial(self.port, baudrate=baudrate, timeout=timeout)
        self.address = address

    def _find_port(self):
        for p in serial.tools.list_ports.comports():
            if 'CH340' in p.description or (p.vid == 0x1A86 and p.pid == 0x7523):
                return p.device
        return None

    @staticmethod
    def _checksum(pkt: bytes) -> int:
        return sum(pkt[1:6]) % 256

    def _send(self, cmd1: int, cmd2: int, data1: int = 0, data2: int = 0):
        pkt = bytearray(7)
        pkt[0] = 0xFF
        pkt[1] = self.address
        pkt[2] = cmd1 & 0xFF
        pkt[3] = cmd2 & 0xFF
        pkt[4] = data1 & 0xFF
        pkt[5] = data2 & 0xFF
        pkt[6] = self._checksum(pkt)
        self.ser.write(pkt)

    # ------------------- 云台方向控制 -------------------
    def left(self, speed: int = 0x20):
        self._send(0x00, 0x04, data1=speed, data2=0)

    def right(self, speed: int = 0x20):
        self._send(0x00, 0x02, data1=speed, data2=0)

    def up(self, speed: int = 0x20):
        self._send(0x00, 0x08, data1=0, data2=speed)

    def down(self, speed: int = 0x20):
        self._send(0x00, 0x10, data1=0, data2=speed)

    def left_up(self, xspeed: int = 0x20, yspeed: int = 0x20):
        self._send(0x00, 0x0C, data1=xspeed, data2=yspeed)

    def right_up(self, xspeed: int = 0x20, yspeed: int = 0x20):
        self._send(0x00, 0x0A, data1=xspeed, data2=yspeed)

    def left_down(self, xspeed: int = 0x20, yspeed: int = 0x20):
        self._send(0x00, 0x14, data1=xspeed, data2=yspeed)

    def right_down(self, xspeed: int = 0x20, yspeed: int = 0x20):
        self._send(0x00, 0x12, data1=xspeed, data2=yspeed)

    def stop(self):
        """停止云台运动"""
        self._send(0x00, 0x00, 0, 0)

    def close(self):
        self.ser.close()


# ------------------- 测试 -------------------
if __name__ == "__main__":
    ctrl = PelcoDPTZ(address=1)
    ctrl.left_up()   # 速度 0x30
    time.sleep(1)
    ctrl.stop()

    ctrl.close()
