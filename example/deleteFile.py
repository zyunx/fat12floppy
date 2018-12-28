import sys
sys.path.insert(1, '..')

import fat12floppy

floppy = fat12floppy.Fat12Floppy('A.IMG')
floppy.list()
floppy.deleteFile('DISKVOL.TXT')
floppy.deleteFile('DOS71_2S.PAK')
print("After delete files:")
floppy.list()
floppy.saveImage('AM.IMG')

