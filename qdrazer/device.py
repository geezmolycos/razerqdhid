import ctypes
import struct
from enum import Enum

from . import protocol as pt

class Device:
    
    def send(self, report):
        raise NotImplementedError
    
    def recv(self):
        raise NotImplementedError
    
    def send_recv(self, report, *, wait_power=0):
        raise NotImplementedError
    
    def sr_with(self, full_command, fmt, *args, **kwargs):
        '''
        Example:
            sr_with(0x0688, '>HI', 123) sets H to 123 and returns I
        '''
        size = struct.calcsize(fmt)
        zero_unpack = struct.unpack(fmt, bytes(size))
        entries = len(zero_unpack)
        r = pt.Report.new((full_command >> 8) & 0xff, full_command & 0xff, size)
        r.arguments[:size] = struct.pack(fmt, *args, *zero_unpack[len(args):])
        rr = self.send_recv(r, **kwargs)
        return struct.unpack(fmt, bytes(rr.arguments[:size]))[len(args):]

    def set_device_mode(self, mode, param=0):
        # 0: normal, 1: bootloader, 2: test, 3: driver
        self.sr_with(0x0004, '>BB', mode.value, param)
    def get_device_mode(self):
        mode, param = self.sr_with(0x0084, '>BB')
        return pt.DeviceMode(mode), param

    def get_serial(self):
        return self.sr_with(0x0082, '>16s')[0].rstrip(b'\x00')

    def get_firmware_version(self):
        return self.sr_with(0x0081, '>4B')

    def set_scroll_mode(self, mode: pt.ScrollMode, *, profile=pt.Profile.CURRENT):
        self.sr_with(0x0214, '>BB', profile.value, mode.value)
    def get_scroll_mode(self, *, profile=pt.Profile.CURRENT):
        mode = self.sr_with(0x0294, '>BB', profile.value)
        return pt.Profile(mode)
    
    def set_scroll_acceleration(self, is_on: bool, *, profile=pt.Profile.CURRENT):
        self.sr_with(0x0216, '>BB', profile.value, int(is_on))
    def get_scroll_acceleration(self, *, profile=pt.Profile.CURRENT):
        return bool(self.sr_with(0x0296, '>BB', profile.value)[0])
    
    def set_scroll_smart_reel(self, is_on: bool, *, profile=pt.Profile.CURRENT):
        self.sr_with(0x0217, '>BB', profile.value, int(is_on))
    def get_scroll_smart_reel(self, *, profile=pt.Profile.CURRENT):
        return bool(self.sr_with(0x0297, '>BB', profile.value)[0])

    def set_button_function(self, fn, button, hypershift=pt.Hypershift.OFF, *, profile=pt.Profile.CURRENT):
        self.sr_with(0x020c, '>BBB7s', profile.value, button.value, hypershift.value, bytes(fn))
    def get_button_function(self, button, hypershift=pt.Hypershift.OFF, *, profile=pt.Profile.CURRENT):
        return pt.ButtonFunction.from_buffer_copy(self.sr_with(0x028c, '>BBB7s', profile.value, button.value, hypershift.value)[0])

    def set_polling_rate(self, delay_ms, *, profile=pt.Profile.CURRENT):
        self.sr_with(0x000e, '>BB', profile.value, delay_ms)
    def get_polling_rate(self, *, profile=pt.Profile.CURRENT):
        return self.sr_with(0x008e, '>BB', profile.value)[0]
    
    def set_dpi_xy(self, dpi, *, profile=pt.Profile.CURRENT):
        self.sr_with(0x0405, '>BHHxx', profile.value, dpi[0], dpi[1])
    def get_dpi_xy(self, *, profile=pt.Profile.CURRENT):
        return self.sr_with(0x0405, '>BHHxx', profile.value)
    
    def set_dpi_stages(self, dpi_stages, active_stage, *, profile=pt.Profile.CURRENT):
        self.sr_with(0x0406, '>BBB35s', profile.value, active_stage, len(dpi_stages),
                     b''.join(struct.pack('>BHHxx', i, x, y) for i, (x, y) in enumerate(dpi_stages + [(0, 0)] * (5-len(dpi_stages)))))
    def get_dpi_stages(self, *, profile=pt.Profile.CURRENT):
        active_stage, len_dpi_stages, dpi_stages = self.sr_with(0x0486, '>BBB35s', profile.value)
        dpi_stages = [struct.unpack('>BHHxx', bytes(x))[1:] for x in zip(*[iter(dpi_stages[:7*len_dpi_stages])] * 7)]
        return dpi_stages, active_stage

    def get_flash_usage(self):
        return self.sr_with(0x068e, '>HIII')
    
    def wait_device_ready(self):
        self.sr_with(0x0086, '>xxx', wait_power=4)
        self.sr_with(0x0086, '>xx')
        return True
    
    def get_profile_total_count(self):
        return self.sr_with(0x058a, '>B')[0]
    
    def get_profile_available_count(self):
        return self.sr_with(0x0580, '>B')[0]
    
    def get_profile_list(self):
        length = self.get_profile_available_count()
        _, *l = self.sr_with(0x0581, f'>B{length}B')
        return l
    
    def new_profile(self, profile):
        self.sr_with(0x0502, '>B', profile.value)
    
    def delete_profile(self, profile):
        self.sr_with(0x0503, '>B', profile.value)
    
    def get_profile_info(self, profile):
        data = b''
        size, chunk = self.sr_with(0x0588, '>BHH64s', profile.value, len(data))
        while size - len(data) > 64:
            data += chunk
            _, chunk = self.sr_with(0x0588, '>BHH64s', profile.value, len(data))
        data += chunk[:size-len(data)]
        return data
    
    def set_profile_info(self, profile, data):
        size = len(data)
        while len(data) > 0:
            self.sr_with(0x0508, f'>BHH{len(data[:64])}s', profile.value, size - len(data), size, data[:64])
            data = data[64:]
    
    def get_macro_count(self):
        return self.sr_with(0x0680, '>H')[0]

    def get_macro_list(self):
        data = []
        size, *chunk = self.sr_with(0x068b, '>HH32H', len(data))
        while size - len(data) > 32:
            data += chunk
            _, *chunk = self.sr_with(0x068b, '>HH32H', len(data))
        data += chunk[:size-len(data)]
        return data
    
    def get_macro_info(self, macro_id):
        data = b''
        size, chunk = self.sr_with(0x068c, '>HHH64s', macro_id, len(data))
        while size - len(data) > 64:
            data += chunk
            _, chunk = self.sr_with(0x068c, '>HHH64s', macro_id, len(data))
        data += chunk[:size-len(data)]
        return data

    def set_macro_info(self, macro_id, data):
        size = len(data)
        while len(data) > 0:
            self.sr_with(0x060c, f'>HHH{len(data[:64])}s', macro_id, size - len(data), size, data[:64])
            data = data[64:]
    
    def delete_macro(self, macro_id):
        self.sr_with(0x0603, '>H', macro_id)
    
    def get_macro_size(self, macro_id):
        return self.sr_with(0x0688, '>HI', macro_id)[0]
    
    def set_macro_size(self, macro_id, length):
        self.sr_with(0x0608, '>HI', macro_id, length)
        
    def get_macro_function(self, macro_id):
        size = self.get_macro_size(macro_id)
        data = b''
        while size - len(data) > 0:
            chunk = self.sr_with(0x0689, '>HIB64s', macro_id, len(data), 64)[0]
            data += chunk[:size-len(data)]
        return data
    
    def set_macro_function(self, macro_id, data):
        size = len(data)
        self.set_macro_size(macro_id, size)
        while len(data) > 0:
            self.sr_with(0x0609, f'>HIB{len(data[:64])}s', macro_id, size - len(data), len(data[:64]), data[:64])
            data = data[64:]
