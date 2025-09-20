import hid

from qdrazer.device import Device
import qdrazer.protocol as pt
from time import sleep

class BasiliskV3Device(Device):
    vid = 0x1532
    pid = 0x0099
    ifn = 3
    
    def connect(self, nth=1, path=None):
        self.path = path
        if self.path is None:
            ith = 0
            for it in hid.enumerate():
                if it['usage_page'] == 12 and tuple(it.get('fio_count') or ()) == (0, 0, 0):
                    # workaround for webhid which cannot get ifn
                    it['interface_number'] = self.ifn
                if it['usage_page'] == 12 and tuple(it.get('fio_count') or ()) == (1, 0, 0) and it['interface_number'] == -1:
                    # workaround for webhid returning ifn as -1 on Linux ungoogled chromium
                    it['interface_number'] = self.ifn
                if self.vid == it['vendor_id'] and self.pid == it['product_id'] and it['interface_number'] == self.ifn:
                    ith += 1
                    if nth == ith:
                        self.path = it['path']
                        break

        if self.path is None:
            raise RuntimeError('No matching device')
        print('ok', self.path)
        self.hid_device = hid.Device(path=self.path)
    
    def close(self):
        self.hid_device.close()
    
    def get_info_manufacturer(self):
        return self.hid_device.manufacturer
    
    def get_info_product(self):
        return self.hid_device.product
    
    def get_info_serial(self):
        return self.hid_device.serial
    
    def print_info(self):
        print(f"device manufacturer: {self.hid_device.manufacturer}")
        print(f"product: {self.hid_device.product}")
        print(f"serial: {self.hid_device.serial}")

        print(self.hid_device.get_indexed_string(1))
        print(self.hid_device.get_indexed_string(2))
    
    def send(self, report):
        report.calculate_crc()
        send_data = b'\x00' + bytes(report)
        self.hid_device.send_feature_report(send_data)
    
    def recv(self):
        data = self.hid_device.get_feature_report(0, 91)
        data = data[1:] # remove report id
        return pt.Report.from_buffer(bytearray(data))
    
    def send_recv(self, report, *, wait_power=0):
        self.send(report)
        rr = report
        if wait_power is None:
            return rr
        for i in range(15 * (wait_power + 1)):
            sleep(0.01 * (i + 1)) # each iteration wait longer
            rr = self.recv()
            if not (rr.command_class == report.command_class and bytes(rr.command_id) == bytes(report.command_id)):
                raise pt.RazerException('command does not match, please close other programs using this device', rr)
            if rr.status == pt.Status.OK:
                return rr
            elif rr.status == pt.Status.BUSY:
                continue
            else:
                raise pt.RazerException(f'report execution failed {rr.status}', rr)
        raise pt.RazerException('report timeout', rr)

if __name__ == '__main__':
    original_sr_with = BasiliskV3Device.sr_with
    def sr_with(self, *args, **kwargs):
        print(f's: {hex(args[0])} {args[1:]}, {kwargs}')
        r = original_sr_with(self, *args, **kwargs)
        print(f'r: {r}')
        return r
    BasiliskV3Device.sr_with = sr_with
    device = BasiliskV3Device()
    device.connect()
    device.set_led_effect(pt.LedRegion.ALL, pt.LedEffect.CUSTOM, 0)
    device.set_led_brightness(pt.LedRegion.ALL, 0xff)
    for p in range(11):
        c = [(0, 0, 0)] * 11
        c[p] = (0, 255, 0)
        device.set_led_static(c)
        sleep(0.3)
    print(device.get_led_effect(pt.LedRegion.LOGO))