import sys
sys.path.insert(1, '..')

import fat12floppy

floppy = fat12floppy.Fat12Floppy('AM.IMG')
floppy.list()
print("After insert files:")
with open('masm5/MASM.EXE', 'rb') as f:
    data = f.read()
floppy.insertFile('MASM.EXE', data)
floppy.list()
floppy.saveImage('A2.IMG')

