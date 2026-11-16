"""Exercise native protocol and movement guards without connecting to a printer."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

HERE = Path(__file__).parent


def load_bridge():
    common = types.ModuleType('bridge_test.common')
    common.RequestType = types.SimpleNamespace(GET=1, POST=2)
    websocket = types.ModuleType('tornado.websocket')
    websocket.websocket_connect = AsyncMock()
    modules = {'bridge_test.common': common, 'tornado.websocket': websocket}
    spec = importlib.util.spec_from_file_location('bridge_test.components.k2_device', HERE / 'k2_device.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


bridge = load_bridge()


def slot_info():
    return {'materialBoxs': [
        {'id': 0, 'type': 1, 'materials': [
            {'id': 0, 'state': 1, 'type': 'PLA', 'color': '#ff0000'}]},
        {'id': 1, 'type': 0, 'state': 1, 'humidity': 23, 'materials': [
            {'id': 0, 'state': 2, 'type': 'PETG', 'name': 'Green', 'color': 'FF00FF00', 'percent': 75},
            {'id': 1, 'state': 0, 'type': '', 'color': 'invalid'}]},
    ]}


class Request:
    def __init__(self, **params):
        self.params = params

    def get_str(self, key):
        return self.params[key]

    def get_int(self, key):
        return self.params[key]


class ProtocolTests(unittest.TestCase):
    def test_snapshots_support_external_and_cfs_without_treating_rfid_as_active(self):
        slots = bridge.slots_from_info(slot_info())
        self.assertEqual([s['label'] for s in slots], ['Spool Holder', '1A', '1B'])
        self.assertEqual(slots[1]['color'], '#00FF00')
        self.assertEqual(slots[1]['humidity'], 23)
        self.assertFalse(slots[2]['occupied'])
        self.assertIsNone(slots[2]['percent'])
        self.assertNotIn('active', slots[1])
        self.assertEqual(bridge.slots_from_info({'materialBoxs': []}), [])

    def test_invalid_ids_colors_percentages_and_disconnected_boxes(self):
        info = slot_info()
        info['materialBoxs'][1]['state'] = 0
        self.assertEqual(len(bridge.slots_from_info(info)), 1)
        for value in (None, True, '50', -1, 101, float('nan'), float('inf')):
            self.assertIsNone(bridge.percentage(value))
        for value in (None, [], {'materialBoxs': 'bad'}, {'materialBoxs': [None, {}]}):
            self.assertEqual(bridge.slots_from_info(value), [])

    def test_rc1_native_seven_digit_colors(self):
        for reported, expected in [('#0000000', '#000000'), ('#000ff7f', '#00ff7f'),
                                   ('#0ff0000', '#ff0000')]:
            info = slot_info()
            info['materialBoxs'][1]['materials'][0]['color'] = reported
            self.assertEqual(bridge.slots_from_info(info)[1]['color'], expected)


class CommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api = types.SimpleNamespace(run_gcode=AsyncMock(), query_objects=AsyncMock(
            return_value={'print_stats': {'state': 'standby'}}))
        self.connection = types.SimpleNamespace(is_ready=lambda: True)
        self.server = Mock()
        self.server.lookup_component.side_effect = lambda name: {
            'klippy_connection': self.connection, 'klippy_apis': self.api}[name]
        self.server.error.side_effect = lambda message, code: RuntimeError(message)
        config = Mock()
        config.get_server.return_value = self.server
        self.device = bridge.K2Device(config)
        self.ws = types.SimpleNamespace(write_message=AsyncMock(), close=Mock())
        self.device.ws = self.ws
        self.device.raw = dict(state=0, feedState=0, boxsInfo=slot_info(),
                               modelFanPct=0, caseFanPct=50, auxiliaryFanPct=100)
        self.device.seen = {key: time.monotonic() for key in self.device.raw}
        self.device.last_message = time.monotonic()

    def test_notification_name_matches_the_fluidd_socket_handler(self):
        self.server.register_notification.assert_called_once_with(
            'k2_device:status_changed', 'k2_device_status_changed')

    def test_native_deltas_keep_unchanged_zero_fans_and_idle_flags_valid(self):
        for key in ('state', 'feedState', 'modelFanPct', 'caseFanPct', 'auxiliaryFanPct'):
            self.device.seen[key] = time.monotonic() - 60
        self.assertEqual(self.device.status()['fans']['model'], 0)
        self.assertTrue(self.device.status()['can_feed'])
        self.device.last_message = time.monotonic() - 11
        self.assertIsNone(self.device.status()['fans']['model'])
        self.assertFalse(self.device.status()['can_feed'])

    async def test_exact_native_filament_payload_and_no_repeat(self):
        request = Request(box_id=1, slot_id=0, action='feed')
        self.assertEqual(await self.device._filament_request(request), {'sent': True})
        sent = json.loads(self.ws.write_message.call_args.args[0])
        self.assertEqual(sent, {'method': 'set', 'params': {
            'feedInOrOut': {'boxId': 1, 'materialId': 0, 'isFeed': 1}}})
        with self.assertRaises(RuntimeError):
            await self.device._filament_request(request)
        self.ws.write_message.assert_awaited_once()

    async def test_retract_external_payload(self):
        await self.device._filament_request(Request(box_id=0, slot_id=0, action='retract'))
        self.assertEqual(json.loads(self.ws.write_message.call_args.args[0])['params'], {
            'feedInOrOut': {'boxId': 0, 'materialId': 0, 'isFeed': 0}})

    async def test_fan_indexes_match_creality_print(self):
        for fan, index in [('model', 0), ('case', 1), ('side', 2)]:
            await self.device._fan_request(Request(fan=fan, speed=50))
            self.api.run_gcode.assert_awaited_with(f'M106 P{index} S128')
        for fan, speed in [('unknown', 50), ('model', -1), ('model', 101)]:
            with self.assertRaises(RuntimeError):
                await self.device._fan_request(Request(fan=fan, speed=speed))

    async def test_print_pause_native_busy_stale_and_empty_slot_refuse_movement(self):
        request = Request(box_id=1, slot_id=0, action='feed')
        for state in ('printing', 'paused', 'unknown'):
            self.api.query_objects.return_value = {'print_stats': {'state': state}}
            with self.assertRaises(RuntimeError):
                await self.device._filament_request(request)
        self.api.query_objects.return_value = {'print_stats': {'state': 'standby'}}
        for field, value in [('state', 1), ('feedState', 1)]:
            old = self.device.raw[field]
            self.device.raw[field] = value
            with self.assertRaises(RuntimeError):
                await self.device._filament_request(request)
            self.device.raw[field] = old
        with self.assertRaises(RuntimeError):
            await self.device._filament_request(Request(box_id=1, slot_id=1, action='feed'))
        self.device.seen['boxsInfo'] = time.monotonic() - 11
        self.assertFalse(self.device.status()['can_feed'])
        self.assertEqual(self.device.status()['slots'], [])
        with self.assertRaises(RuntimeError):
            await self.device._filament_request(request)
        self.ws.write_message.assert_not_awaited()

    async def test_disconnect_and_firmware_restart_disable_controls(self):
        self.connection.is_ready = lambda: False
        with self.assertRaises(RuntimeError):
            await self.device._fan_request(Request(fan='model', speed=100))
        self.device.ws = None
        status = self.device.status()
        self.assertFalse(status['connected'])
        self.assertFalse(status['can_feed'])
        self.assertEqual(status['slots'], [])
        self.assertIsNone(status['fans']['model'])

    async def test_disconnect_during_query_does_not_send(self):
        async def disconnect(*args):
            self.device.ws = None
            return {'print_stats': {'state': 'standby'}}
        self.api.query_objects.side_effect = disconnect
        with self.assertRaises(RuntimeError):
            await self.device._filament_request(Request(box_id=1, slot_id=0, action='feed'))
        self.ws.write_message.assert_not_awaited()

    async def test_transport_failure_never_retries_movement(self):
        self.ws.write_message.side_effect = OSError('closed')
        with self.assertRaises(OSError):
            await self.device._filament_request(Request(box_id=1, slot_id=0, action='feed'))
        self.assertTrue(self.device.status()['pending'])
        self.ws.write_message.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
