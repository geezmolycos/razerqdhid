import sys
import types
import unittest
from pathlib import Path


PYTHON_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PYTHON_ROOT))

fake_hid = types.ModuleType('hid')
fake_hid.enumerate = lambda: []
fake_hid.device = lambda: None
sys.modules['hid'] = fake_hid

from basilisk_v3.device import (  # noqa: E402
    BasiliskV3Pro35KPhantomGreenDevice,
    BasiliskV3ProDevice,
    WEBHID_DEVICE_CLASSES,
)


class LegacyHidDevice:
    def __init__(self):
        self.path = None

    def open_path(self, path):
        self.path = path


class DeviceDetectionTest(unittest.TestCase):
    def tearDown(self):
        fake_hid.enumerate = lambda: []
        fake_hid.device = lambda: None
        if hasattr(fake_hid, 'Device'):
            del fake_hid.Device

    def test_wired_and_wireless_product_ids_are_detected(self):
        self.assertEqual(BasiliskV3ProDevice()._product_ids(), (0x00AA, 0x00AB))
        self.assertEqual(
            BasiliskV3Pro35KPhantomGreenDevice()._product_ids(),
            (0x00D6, 0x00D7),
        )

    def test_phantom_green_uses_interface_zero(self):
        self.assertEqual(BasiliskV3Pro35KPhantomGreenDevice.ifn, 0)

    def test_phantom_green_is_not_advertised_for_webhid(self):
        self.assertNotIn(
            BasiliskV3Pro35KPhantomGreenDevice,
            WEBHID_DEVICE_CLASSES,
        )

    def test_phantom_green_wireless_opens_with_legacy_hidapi(self):
        path = b'1-2:1.0'
        fake_hid.enumerate = lambda: [{
            'path': path,
            'vendor_id': 0x1532,
            'product_id': 0x00D7,
            'interface_number': 0,
            'usage_page': 0,
            'fio_count': (),
        }]
        legacy_device = LegacyHidDevice()
        fake_hid.device = lambda: legacy_device

        device = BasiliskV3Pro35KPhantomGreenDevice()
        device.connect()

        self.assertIs(device.hid_device, legacy_device)
        self.assertEqual(legacy_device.path, path)

    def test_modern_hid_api_remains_supported(self):
        path = b'1-2:1.0'
        fake_hid.enumerate = lambda: [{
            'path': path,
            'vendor_id': 0x1532,
            'product_id': 0x00D6,
            'interface_number': 0,
            'usage_page': 0,
            'fio_count': (),
        }]
        modern_device = object()
        fake_hid.Device = lambda *, path: modern_device

        device = BasiliskV3Pro35KPhantomGreenDevice()
        device.connect()

        self.assertIs(device.hid_device, modern_device)


if __name__ == '__main__':
    unittest.main()
