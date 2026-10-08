#!/usr/bin/env python3
# Lab3 - BLE Central on Raspberry Pi 3 (bluepy)
# Usage: sudo python3 ble_central.py
from bluepy.btle import Scanner, DefaultDelegate, Peripheral, UUID, BTLEException
import struct
import sys

CCCD_UUID = UUID(0x2902)
CCCD_VALUE = 0x0002          # 0x0001 = Notification, 0x0002 = Indication
SYSTEM_SERVICES = (UUID(0x1800), UUID(0x1801))


class ScanDelegate(DefaultDelegate):
    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev:
            print("Discovered device", dev.addr)
        elif isNewData:
            print("Received new data from", dev.addr)


class NotifyDelegate(DefaultDelegate):
    def handleNotification(self, cHandle, data):
        print("[Notify/Indicate] handle=0x%04x data=%s" % (cHandle, data.hex()))


def scan():
    scanner = Scanner().withDelegate(ScanDelegate())
    devices = list(scanner.scan(10.0))
    for i, dev in enumerate(devices):
        name = dev.getValueText(9) or dev.getValueText(8) or "(unknown)"
        print("%2d: %s (%s), RSSI=%d dB, name=%s"
              % (i, dev.addr, dev.addrType, dev.rssi, name))
    return devices


def pick_char(dev):
    # Pick automatically: waiting for user input here lets the phone drop the link
    found = None
    for svc in dev.getServices():
        print("Service", svc.uuid)
        for ch in svc.getCharacteristics():
            props = ch.propertiesToString()
            print("    %s  props=%s  handle=0x%04x" % (ch.uuid, props, ch.getHandle()))
            # Skip Generic Access/Attribute (e.g. Service Changed 0x2A05)
            if found is None and "INDICATE" in props and svc.uuid not in SYSTEM_SERVICES:
                found = ch
    if found is None:
        sys.exit("No characteristic with INDICATE found")
    print("==> Using characteristic", found.uuid)
    return found


def find_cccd_handle(ch):
    try:
        descs = ch.getDescriptors(forUUID=CCCD_UUID)
        if descs:
            return descs[0].handle
    except BTLEException:
        pass
    # CCCD normally sits right after the characteristic value handle
    return ch.getHandle() + 1


def main():
    devices = scan()
    if not devices:
        sys.exit("No device found")
    target = devices[int(input("Enter device number: "))]

    # Connecting often fails in a crowded 2.4GHz environment, so retry a few times
    for attempt in range(1, 4):
        print("Connecting to %s (try %d/3)" % (target.addr, attempt))
        try:
            dev = Peripheral(target.addr, target.addrType)
            break
        except BTLEException as e:
            print("Connect failed:", e)
    else:
        sys.exit("Could not connect. Restart bluetooth and try again.")
    dev.setDelegate(NotifyDelegate())

    try:
        ch = pick_char(dev)

        cccd = find_cccd_handle(ch)

        print("CCCD handle=0x%04x, old value=%s" % (cccd, dev.readCharacteristic(cccd).hex()))
        # CCCD is 16-bit little-endian: 0x0002 -> b'\x02\x00'
        dev.writeCharacteristic(cccd, struct.pack("<H", CCCD_VALUE), withResponse=True)
        print("CCCD written 0x%04x, read back=%s" % (CCCD_VALUE, dev.readCharacteristic(cccd).hex()))

        if ch.supportsRead():
            print("Characteristic value:", ch.read())

        print("Waiting for notifications/indications (Ctrl+C to stop)...")
        while True:
            if not dev.waitForNotifications(5.0):
                print("...waiting")
    except KeyboardInterrupt:
        pass
    except BTLEException as e:
        print("BLE error:", e)
    finally:
        dev.disconnect()


if __name__ == "__main__":
    main()
