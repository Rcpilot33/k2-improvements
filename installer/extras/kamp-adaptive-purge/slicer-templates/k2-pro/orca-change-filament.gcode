{if layer_num >= 0}
G2 Z{z_after_toolchange + 0.4} I0.86 J0.86 P1 F10000 ; spiral lift
{if print_sequence == "by object"}
G0 Z{max_layer_z + 0.8} F900
{endif}
G1 X0 Y160 F30000
{endif}
