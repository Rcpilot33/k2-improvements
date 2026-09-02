# Creality K2 Plus SAFE_MOVE_Z compatibility for Cartographer
#
# The stock prtouch_v3 extension owns SAFE_MOVE_Z and reports the completed
# travel through virtual_sdcard.run_dis.  Creality's master-server waits for
# that status field before it continues preparing a consecutive print.
# Cartographer replaces prtouch_v3, so both parts of that contract must be
# supplied here.
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging
import math


class K2SafeMoveZ:
    TARGET_Z = 20.0
    TARGET_TOLERANCE = 0.25
    COMPLETION_TOLERANCE = 0.05

    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')

        printer_config = config.getsection('printer')
        self.max_z_velocity = printer_config.getfloat(
            'max_z_velocity', above=0.0)
        stepper_z_config = config.getsection('stepper_z')
        self.position_min = stepper_z_config.getfloat(
            'position_min', 0.0)
        self.position_max = stepper_z_config.getfloat('position_max')

        self.gcode.register_command(
            'SAFE_MOVE_Z', self.cmd_SAFE_MOVE_Z,
            desc=self.cmd_SAFE_MOVE_Z_help)

    cmd_SAFE_MOVE_Z_help = (
        "Handle Creality's guarded inter-print Z=20 safe move")

    def _require_idle(self, gcmd):
        print_stats = self.printer.lookup_object('print_stats')
        eventtime = self.printer.get_reactor().monotonic()
        state = print_stats.get_status(eventtime).get('state', '')
        if state in ('printing', 'paused'):
            raise gcmd.error(
                '[SAFE_MOVE_Z] Refusing inter-print move while a print is '
                'active')

    def cmd_SAFE_MOVE_Z(self, gcmd):
        state = gcmd.get_int('STA', 0)
        if state == 0:
            gcmd.respond_info(
                '[SAFE_MOVE_Z] Stop/cleanup request acknowledged')
            return
        if state != 1:
            raise gcmd.error(
                '[SAFE_MOVE_Z] Unsupported STA=%d' % (state,))

        distance = gcmd.get_float('DIS')
        speed = gcmd.get_float('SPD')
        if not math.isfinite(distance):
            raise gcmd.error('[SAFE_MOVE_Z] DIS must be finite')
        if (not math.isfinite(speed) or speed <= 0.0
                or speed > self.max_z_velocity):
            raise gcmd.error(
                '[SAFE_MOVE_Z] Refusing invalid speed %.3fmm/s' % (speed,))

        self._require_idle(gcmd)
        eventtime = self.printer.get_reactor().monotonic()
        toolhead = self.printer.lookup_object('toolhead')
        if 'z' not in toolhead.get_status(eventtime).get('homed_axes', ''):
            raise gcmd.error(
                '[SAFE_MOVE_Z] Refusing move because Z is not homed')

        start_z = toolhead.get_position()[2]
        target_z = start_z + distance
        if abs(target_z - self.TARGET_Z) > self.TARGET_TOLERANCE:
            raise gcmd.error(
                '[SAFE_MOVE_Z] Refusing unexpected target Z=%.3f' %
                (target_z,))
        if target_z < self.position_min or target_z > self.position_max:
            raise gcmd.error(
                '[SAFE_MOVE_Z] Target Z=%.3f is outside machine limits' %
                (target_z,))

        virtual_sdcard = self.printer.lookup_object('virtual_sdcard')
        # Clear the prior operation before starting.  master-server polls this
        # field and must not mistake a previous safe move for this one.
        virtual_sdcard.run_dis = 0.0

        gcmd.respond_info(
            '[SAFE_MOVE_Z] Moving Z %.3fmm to %.3fmm at %.3fmm/s' %
            (distance, target_z, speed))
        toolhead.manual_move([None, None, target_z, None], speed)
        toolhead.wait_moves()

        end_z = toolhead.get_position()[2]
        if abs(end_z - target_z) > self.COMPLETION_TOLERANCE:
            raise gcmd.error(
                '[SAFE_MOVE_Z] Move stopped at Z=%.3f; expected Z=%.3f' %
                (end_z, target_z))

        completed_distance = end_z - start_z
        # This is the stock prtouch_v3 completion contract.  Publishing only
        # after wait_moves() prevents master-server from continuing while the
        # bed is still moving.
        virtual_sdcard.run_dis = completed_distance
        logging.info(
            '[SAFE_MOVE_Z] completed distance=%.6f start_z=%.6f end_z=%.6f',
            completed_distance, start_z, end_z)
        gcmd.respond_info(
            '[SAFE_MOVE_Z] Completed Z move; run_dis=%.3f' %
            (completed_distance,))


def load_config(config):
    return K2SafeMoveZ(config)
