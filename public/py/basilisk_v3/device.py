import hid

from qdrazer.device import Device
import qdrazer.protocol as pt
from time import sleep

class BasiliskV3Device(Device):
    vid = 0x1532
    pid = 0x0099
    ifn = 3

    def _product_ids(self):
        product_ids = [self.pid]
        if hasattr(self, 'pid_wireless'):
            product_ids.append(self.pid_wireless)
        return tuple(product_ids)
    
    def _fix_interface_number(self, it):
        """Hook for subclasses to fix interface detection issues."""
        fio = tuple(it.get("fio_count") or ())
        if it['usage_page'] == 12 and fio == (0, 0, 0):
            it['interface_number'] = self.ifn
        if it['usage_page'] == 12 and fio == (1, 0, 0) and it['interface_number'] == -1:
            it['interface_number'] = self.ifn
        return it
    
    def connect(self, nth=1, path=None):
        self.path = path
        if self.path is None:
            ith = 0
            for it in hid.enumerate():
                # Call the hook to allow subclasses to modify 'it'
                it = self._fix_interface_number(it)

                if self.vid == it['vendor_id'] and it['product_id'] in self._product_ids() and it['interface_number'] == self.ifn:
                    ith += 1
                    if nth == ith:
                        self.path = it['path']
                        break

        if self.path is None:
            raise RuntimeError('No matching device')
        print('ok', self.path)
        if hasattr(hid, 'Device'):
            self.hid_device = hid.Device(path=self.path)
        else:
            self.hid_device = hid.device()
            self.hid_device.open_path(self.path)
    
    def close(self):
        self.hid_device.close()
    
    def get_info_manufacturer(self):
        if hasattr(self.hid_device, 'manufacturer'):
            return self.hid_device.manufacturer
        return self.hid_device.get_manufacturer_string()
    
    def get_info_product(self):
        if hasattr(self.hid_device, 'product'):
            return self.hid_device.product
        return self.hid_device.get_product_string()
    
    def get_info_serial(self):
        if hasattr(self.hid_device, 'serial'):
            return self.hid_device.serial
        return self.hid_device.get_serial_number_string()
    
    def print_info(self):
        print(f"device manufacturer: {self.get_info_manufacturer()}")
        print(f"product: {self.get_info_product()}")
        print(f"serial: {self.get_info_serial()}")

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


class BasiliskV3ProDevice(BasiliskV3Device):
    """
    Basilisk V3 Pro with PID 0x00AA (wired) or 0x00AB (wireless)
    Supports the same protocol as BasiliskV3Device but with different PID
    """

    vid = 0x1532
    pid = 0x00AA
    pid_wireless = 0x00AB
    ifn = 3
    
    def _fix_interface_number(self, it):
        # Run base fixes first
        it = super()._fix_interface_number(it)
        
        # Workaround for Brave browser (tested with Brave 1.85.118 based on Chromium: 143.0.7499.169)
        # Not sure if this is needed for all devices or just my combination of hardware and software.
        # V3 Pro on this hardware+software combination reports as it["usage_page"]===1 instead of 12
        fio = tuple(it.get("fio_count") or ())
        if it.get("interface_number", -1) == -1 and it["product_id"] in self._product_ids() and self.vid == it["vendor_id"]:
            if len(fio) >= 1 and fio[0] > 0:
                it["interface_number"] = self.ifn
        return it


class BasiliskV3Pro35KPhantomGreenDevice(BasiliskV3ProDevice):
    """Basilisk V3 Pro 35K Phantom Green Edition, wired or wireless."""

    pid = 0x00D6
    pid_wireless = 0x00D7
    ifn = 0


WEBHID_DEVICE_CLASSES = (
    BasiliskV3ProDevice,
    BasiliskV3Device,
)

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
