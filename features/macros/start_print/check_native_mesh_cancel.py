"""Hardware-free contract check against Creality's compiled PR Touch mesh.

Run on the printer with Python 3.9 from this directory. Imports the driver class,
but never constructs its real config/printer/MCU objects. Every probe, toolhead,
command, configuration, and movement dependency is a fake. No connection to
live Klippy, motion, heater command, or configuration write is performed.
"""

import sys, traceback
sys.path.insert(0, '/usr/share/klipper/klippy')
from extras import prtouch_v3_wrapper as module
from gcode import CancelError
class Missing:
    def __getattr__(self, name): raise AttributeError('FIXTURE NEEDS: '+type(self).__name__+'.'+name)
class Reactor(Missing):
    def monotonic(self): return 0.
class Probe(Missing):
    lift_speed=5.
    sample_retract_dist=2.
    samples_tolerance=.1
    samples_retries=0
    samples_result='median'
    speed=5.
    sample_count=1
    def run_probe(self,gcmd):
        print('FAKE COMPLETE SAMPLE THEN CANCEL')
        self.gcode.cancel_pending=True
        return [175.,175.,0.]
    def get_offsets(self): return (0.,0.,0.)
    def get_lift_speed(self, gcmd=None): return 5.
    def multi_probe_begin(self):
        print('FAKE PROBE BEGIN')
        self.multi_probe_pending=True
    def multi_probe_end(self):
        print('NATIVE PROBE END WITH FAKE HARDWARE')
        self.multi_probe_pending=False
        module.PRTouchEndstopWrapper.multi_probe_end(self.mcu_probe)
class GCode(Missing):
    cancel_error=CancelError
    cancel_pending=False
    def __init__(self): self.commands={}; self.scripts=[]
    def create_gcode_command(self, *args): return FakeCommand()
    def register_command(self,name,handler,**kwargs):
        original=self.commands.pop(name,None)
        if handler is not None: self.commands[name]=handler
        return original
    def respond_info(self,msg): print('FAKE INFO',msg)
    def run_script_from_command(self,script): self.scripts.append(script); print('FAKE GCODE',script)
class Printer(Missing):
    def __init__(self): self.objects=dict(probe=Probe(),gcode=GCode(),toolhead=Toolhead())
    def get_reactor(self): return Reactor()
    def lookup_object(self, name, default=None):
        if name in self.objects: return self.objects[name]
        raise AttributeError('LOOKUP NEEDS: '+name)
class Kin(Missing):
    def set_max_z_accel(self, value): print('FAKE z accel',value)
    def set_max_z_velocity(self, value): print('FAKE z velocity',value)
    def get_max_z_velocity(self): return self.max_z_velocity
    def get_max_z_accel(self): return self.max_z_accel
    max_z_velocity=20.
    max_z_accel=500.
class Toolhead(Missing):
    kin=Kin()
    square_corner_velocity=10.
    max_velocity=300.
    max_accel=5000.
    max_accel_to_decel=5000.
    def __getattr__(self, name):
        if name.startswith('get_max_') or name.startswith('get_square_'):
            print('FAKE getter',name)
            return lambda: 300.
        return super().__getattr__(name)
    def get_max_accel(self): return 5000.
    def get_max_accel_to_decel(self): return 5000.
    def get_max_jerk(self): return 10.
    def get_status(self, eventtime): return dict(max_accel=5000.,max_velocity=300.,square_corner_velocity=10.)
    def get_max_velocity(self): return 300.
    def set_max_accel(self, value): print('FAKE accel',value)
    def set_max_velocity(self, value): print('FAKE velocity',value)
    def get_position(self): return [175.,175.,5.,0.]
    def wait_moves(self): pass
class Settings(Missing):
    def getintlist(self, name, default=None, **kwargs): print('SETTING intlist',name); return (3,3)
    def getfloatlist(self,name,default=None,**kwargs): print('SETTING floatlist',name); return (330.,330.) if name=='mesh_max' else (20.,20.)
    def getsection(self, name): print('SECTION',name); return self
    def getfloat(self, name, default=None, **kwargs): print('SETTING float',name,default); return default if default is not None else 100.
    def getint(self, name, default=None, **kwargs): print('SETTING int',name,default); return default if default is not None else 3
    def get(self, name, default=None): print('SETTING',name,default); return default
class ProbeHelper(Missing):
    probe_points=[(x,y) for y in (20.,175.,330.) for x in (20.,175.,330.)]
    horizontal_move_z=5.
    speed=50.
    probe_offsets=(0.,0.,0.)
    def get_lift_speed(self): return 5.
class BMC(Missing):
    def __init__(self):
        self.probe_helper=ProbeHelper()
        self.mesh_config=dict(x_count=3,y_count=3,min_x=20.,max_x=330.,min_y=20.,max_y=330.)
    def update_config(self,gcmd): pass
    def probe_finalize(self,*args): print('FAKE FINALIZE',args)
class BedMesh(Missing):
    z_mesh=None
    def __init__(self): self.bmc=BMC()
    def get_mesh(self): return None
    def set_mesh(self, mesh): print('FAKE SET MESH',mesh)
class FakeNative(module.PRTouchEndstopWrapper):
    rdy_sped=50.
    def_hmvz_quick=5.
    def_hmvz=5.
    xy_speed=50.
    regional_prtouch_switch=0
    tri_zacc=500.
    tri_zspeed=5.
    probe_speed=5.
    max_z=350.
    msg_show=False
    hot_start=False
    g29flag=False
    g28_ing=False
    g28_stat=0
    g29_stat=0
    isCalibrateFlg=False
    def disturb_ctl(self,*args): print('FAKE DISTURB',args)
    def run_script_from_command(self, script): print('FAKE SCRIPT',script)
    def print_msg(self, title, msg, force=False): print('FAKE MSG',title,msg)
    def gcode_move(self, pos, speed, wait=True, showlog=True): print('FAKE MOVE',pos,speed,wait)
    def delay_s(self, seconds): pass
    def wait_moves(self): pass
    def __init__(self):
        self.printer=Printer()
        self.toolhead=self.printer.lookup_object('toolhead')
        self.config=Settings()
        self.bed_mesh=BedMesh()
        self.phelper=self.bed_mesh.bmc.probe_helper
        self.probe=self.printer.lookup_object('probe')
        self.gcode=self.printer.lookup_object('gcode')
        self.printer.objects['prtouch_v3']=self
        self.probe.mcu_probe=self
        self.probe.gcode=self.gcode
        self.gcode.commands['BED_MESH_CALIBRATE']=self.cmd_BED_MESH_CALIBRATE
    def __getattr__(self, name): raise AttributeError('FIXTURE NEEDS: native.'+name)
class FakeCommand:
    def get(self, name, default=None):
        print('PARAM', name, default)
        return default
    def get_int(self, name, default=None, **kwargs): return self.get(name, default)
    def get_float(self, name, default=None, **kwargs): return self.get(name, default)
    def error(self, message): return RuntimeError(message)
    def respond_info(self, message): print('INFO', message)
class Helper:
    active=True
    def __init__(self, native):
        self.printer,self.gcode=native.printer,native.gcode
    def is_cancel_pending(self): return self.gcode.cancel_pending
if 'guard_namespace' not in globals():
    import k2_start_print_fast_stop
    guard_namespace = vars(k2_start_print_fast_stop)
native_fixture=FakeNative()
guard=guard_namespace['PRTouchMeshCancel'](Helper(native_fixture))
guard.install()
assert guard.installed
try:
    guard.cmd_mesh(FakeCommand())
except CancelError:
    assert guard.mesh_depth==0
    assert not native_fixture.probe.multi_probe_pending
    assert not native_fixture.g29_stat
    assert not native_fixture.isCalibrateFlg
    assert len(native_fixture.gcode.scripts)==1
    print('PASS: actual compiled mesh unwound after completed fake sample; session and calibration flags restored; partial finalizer not reached')
else: raise AssertionError('compiled mesh did not propagate cancellation')
