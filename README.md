# Digital_Pattern_Generator_DPG1
User Wiki and documentation for S-Fifteen Instrument's Digital Pattern Generator DPG1

pattgen_loader.py provides a GUI interface for user to convert (.patt convert button) a .patt file to  a 4-word .wrd command list that can be fed into the device.
Load the .wrd file by pressing the .word load button.
The generator.py file is a script made in QO Lab to convert .patt files to .wrd files.
pattgen_class and serial_device provide some basic tools to connect to device via USB-serial.

The .patt file has only three types of commands, sample code in load_atom_redu.patt:

#triggered input_line use_table threshold_counts_per_second if_success_table if_failure_table time_to_trigger [bits to turn on(0-25)]

#sequential [repeat_table(at least 0)] use_table end_table time [bits to turn on(0-25)] 

#conditional input_line use_table if_success_table trigger_width [bits to turn on(0-25)]

Space between inputs of each command.
End .patt file with a dot at the last line.
