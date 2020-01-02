# PATTERN GENERATOR V2 INTERFACE SCRIPT
# Simple interface to read .patt file, convert to 4 word format, and send to device via USB serial.
# Feel free to modify as one sees fit. The structure of the script is similar to counter FPGA script
# to ensure modularity.
# The pattgen_class is used to initiate serial communication.
# The generator script is used to convert .patt to .wrd file, based on Chang Hoong's script from  QO LAB, NUS.
# Script from Chin Chean Lim, 31/12/19.  chinchean.lim@sfifteen.com


import pattgen_class as PG
import generator as GN
import numpy as np
from tkinter import *
from tkinter import ttk
from tkinter import filedialog
import time
import serial.tools.list_ports
import os

def InitDevice(*args):
    loop_flag.set(False)
    started = 1
    deviceAddress = ''
    for idx, device in enumerate(devicelist):
        if set_ports.get() == device:
            deviceAddress = addresslist[idx]
    print("SelectedPort " + deviceAddress)
    pattgen.startport(deviceAddress)
    print(set_ports.get(), "ready to go.")

def on_closing():
    pattgen.closeport()
    root.destroy()

# This allows GUI user to load four word files.
def WordLoad(*args):
    directory = filedialog.askopenfilename(initialdir = "/",title = "Select file",filetypes = (("WORD","*.wrd"),("all files","*.*")))
    print("Load path: " + directory)
    global wordpath
    wordpath = directory
    tableW=open(wordpath, "r")
    #print(tableW.read())
    pattgen.sendtables(tableW.read())

# This allows GUI user to load Patt files.
def PattLoad(*args):
    directory = filedialog.askopenfilename(initialdir = "/",title = "Select file",filetypes = (("PATT","*.patt"),("all files","*.*")))
    print("Patt path: " + directory)
    global pattpath
    pattpath = directory
    oldbase = os.path.splitext(pattpath)
    wordout_path = (oldbase[0]+'.wrd')
    tableP=open(pattpath, "r")
    WordOut = GN.generator(tableP)
    outputfile = open(wordout_path,'w+')
    print("Converted word path: " + wordout_path)
    outputfile.write(WordOut)
    outputfile.close()
    tableP.close()


"""Setting up the main window"""
root = Tk()
root.title("Pattern Generator")
mainframe = ttk.Frame(root, padding="3 3 12 12")
mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
mainframe.columnconfigure(0, weight=1)
mainframe.rowconfigure(0, weight=1)

pattgen = PG.PattGen()

# Device option menu.
portslist = list(serial.tools.list_ports.comports())
devicelist = []
addresslist = []
for port in portslist:
    devicelist.append(port.device + " " + port.description)
    addresslist.append(port.device)
print(devicelist)
set_ports = StringVar(mainframe)
ports_option = ttk.OptionMenu(mainframe, set_ports, devicelist, *devicelist)
ports_option.grid(row=7, padx=2, pady=5, column=2)
ports_option.configure(width=30)
loop_flag = BooleanVar()
loop_flag.set(False)

ttk.Button(mainframe, text="Init Device", command=InitDevice).grid(
    column=4, row=7, sticky=W)
ttk.Button(mainframe, text=".Word Load", command=WordLoad).grid(
    column=4, row=4, sticky=W)
ttk.Button(mainframe, text=".Patt Convert", command=PattLoad).grid(
    column=4, row=5, sticky=W)
ttk.Label(mainframe, text='Select Device',
          font=("Helvetica", 12)).grid(column=1, row=7, sticky=(W))


# padding the space surrounding all the widgets
for child in mainframe.winfo_children():
    child.grid_configure(padx=10, pady=10)

root.protocol("WM_DELETE_WINDOW",on_closing)

# finally we run it!
root.mainloop()