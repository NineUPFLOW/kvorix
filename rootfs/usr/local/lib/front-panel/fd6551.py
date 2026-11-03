
import time

import gpiod
from gpiod.line import Direction, Drive, Value

CHIP, SCL, SDA = "/dev/gpiochip0", 64, 63
HI, LO = Value.ACTIVE, Value.INACTIVE


class FD6551:
    def __init__(self):
        cfg = gpiod.LineSettings(direction=Direction.OUTPUT, drive=Drive.OPEN_DRAIN, output_value=HI)
        self.req = gpiod.request_lines(CHIP, consumer="front-panel", config={(SCL, SDA): cfg})

    def _set(self, line, v):
        self.req.set_value(line, HI if v else LO)

    def _byte(self, b):
        for i in range(7, -1, -1):
            self._set(SDA, (b >> i) & 1)
            self._set(SCL, 1)
            self._set(SCL, 0)
        self._set(SDA, 1)
        self._set(SCL, 1)
        self._set(SCL, 0)

    def cmd(self, c, d):
        self._set(SCL, 1); self._set(SDA, 1)
        self._set(SDA, 0); self._set(SCL, 0)
        self._byte(c); self._byte(d)
        self._set(SDA, 0); self._set(SCL, 1); self._set(SDA, 1)

    def brightness(self, level):
        
        self.cmd(0x48, (((max(0, min(7, level)) + 1) & 7) << 4) | 0x01)

    def write(self, grids):
        
        for i, b in enumerate(grids[:5]):
            self.cmd(0x66 + 2 * i, b & 0xFF)

    def close(self):
        self.req.release()


if __name__ == "__main__":
    d = FD6551()
    d.brightness(7)
    for g in range(5):
        d.write([0] * 5)
        time.sleep(1)
        d.write([0xFF if i == g else 0 for i in range(5)])
        print("ячейка", g, "засвечена", flush=True)
        time.sleep(4)
    d.write([0xFF] * 5)
    print("все ячейки засвечены", flush=True)
    time.sleep(5)
