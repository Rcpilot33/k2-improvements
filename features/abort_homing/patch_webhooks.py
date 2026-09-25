#!/usr/bin/env python
"""Patches webhooks.py to add force_stop_homing endpoint."""
import sys
import re
import os
import shutil
import stat
import tempfile

ENDPOINT_REGISTRATION = '        self.register_endpoint("force_stop_homing", self._handle_force_stop_homing)'

FORCE_STOP_METHOD = '''
    def _handle_force_stop_homing(self, web_request):
        """Force stop homing move without triggering emergency stop"""
        toolhead = self.printer.lookup_object('toolhead')
        gcode = self.printer.lookup_object('gcode')
        if toolhead.special_queuing_state == "Drip" and toolhead.drip_completion:
            toolhead.drip_completion.complete(1)
            gcode.respond_raw("!! Force stop homing triggered - move stopped")
            reactor = self.printer.get_reactor()
            def delayed_motor_off(eventtime):
                stepper_enable = self.printer.lookup_object('stepper_enable')
                stepper_enable.motor_off()
                gcode.respond_raw("!! Motors disabled after homing stop")
                return reactor.NEVER
            reactor.register_timer(delayed_motor_off, reactor.monotonic() + 0.5)
            web_request.send({'stopped': True, 'message': 'Homing stopped'})
        else:
            web_request.send({'stopped': False, 'message': 'Not currently homing'})
'''

NEW_GET_STATUS = '''def get_status(self, eventtime):
        state_message, state = self.printer.get_state_message()
        return {
            'state': state,
            'state_message': state_message,
            'can_force_stop_homing': True
        }'''

def patch_webhooks(filepath):
    try:
        with open(filepath, 'r') as f:
            original_content = f.read()
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return False

    patch_markers = (
        ENDPOINT_REGISTRATION.strip(),
        "def _handle_force_stop_homing(self, web_request):",
        "'can_force_stop_homing': True",
    )
    marker_state = [marker in original_content for marker in patch_markers]
    if all(marker_state):
        print("Already patched, no changes needed.")
        return None
    if any(marker_state):
        print("ERROR: webhooks.py contains a partial abort-homing patch; refusing to double-patch it.")
        return False

    estop_reg = 'self.register_endpoint("emergency_stop", self._handle_estop_request)'
    if estop_reg not in original_content:
        print("ERROR: Could not find 'emergency_stop' endpoint registration.")
        return False
    
    estop_impl = 'def _handle_estop_request(self, web_request):'
    if estop_impl not in original_content:
        print("ERROR: Could not find '_handle_estop_request' method definition.")
        return False

    old_get_status_pattern = r"def get_status\(self, eventtime\):\s+state_message, state = self\.printer\.get_state_message\(\)\s+return \{'state': state, 'state_message': state_message\}"
    if not re.search(old_get_status_pattern, original_content):
        print("ERROR: Could not find standard 'get_status' method implementation.")
        return False

    content = original_content

    new_content = content.replace(estop_reg, estop_reg + '\n' + ENDPOINT_REGISTRATION)
    if new_content == content:
        print("ERROR: Patch 1 (endpoint registration) failed to apply.")
        return False
    content = new_content
    print("  + Added force_stop_homing endpoint registration")

    estop_full_pattern = r'(def _handle_estop_request\(self, web_request\):\s+self\.printer\.invoke_shutdown\("Shutdown due to webhooks request"\))'
    new_content = re.sub(estop_full_pattern, lambda m: m.group(1) + "\n" + FORCE_STOP_METHOD, content)
    if new_content == content:
        print("ERROR: Patch 2 (method definition) failed to apply.")
        return False
    content = new_content
    print("  + Added _handle_force_stop_homing method")

    new_content = re.sub(old_get_status_pattern, NEW_GET_STATUS, content)
    if new_content == content:
        print("ERROR: Patch 3 (get_status update) failed to apply.")
        return False
    content = new_content
    print("  + Updated get_status to include can_force_stop_homing")

    backup_path = str(filepath) + ".before-abort-homing.bak"
    directory = os.path.dirname(os.path.realpath(filepath)) or "."
    mode = stat.S_IMODE(os.stat(filepath).st_mode)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".abort-homing-", dir=directory, text=True
    )
    try:
        if not os.path.exists(backup_path):
            shutil.copy2(filepath, backup_path)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, filepath)
        print("Patch applied successfully!")
        return True
    except Exception as e:
        print(f"Error writing file: {e}")
        return False
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: patch_webhooks.py <path_to_webhooks.py>")
        sys.exit(1)

    filepath = sys.argv[1]
    result = patch_webhooks(filepath)
    if result is None:
        sys.exit(2)
    sys.exit(0 if result else 1)
