import sys
import struct
import datetime

class DirectoryEntry:
    def __init__(self, directoryEntryData):
        self.data = directoryEntryData
        self._parse()

    def fullName(self):
        fileName = self.name.strip()
        fileExt = self.ext.strip()
        if len(fileExt) == 0:
            wholeFileName = fileName
        else:
            wholeFileName = fileName + "." + fileExt
        return wholeFileName

    def isDirectory(self):
        return self.attr & 0x10 == 0x10

    def isDiskLabel(self):
        return self.attr & 0x08 == 0x08

    def isDeleted(self):
        return self.data[0] == 0xE5

    def isEnd(self):
        return self.data[0] == 0

    def _parseLastModTime(self, de):
        tempLastModTime = struct.unpack('<H', de[0x16:0x18])[0]
        lastModSec = 2 * (tempLastModTime & 0x1F)
        tempLastModTime >>= 5
        lastModMin = tempLastModTime & 0x3F
        tempLastModTime >>= 6
        lastModHour = tempLastModTime & 0x1F
        self.lastModTime = '{:02}:{:02}:{:02}'.format(
                lastModHour, lastModMin, lastModSec)

    def _parseLastModDate(self, de):
        tempLastModDate = struct.unpack('<H', de[0x18:0x1A])[0]
        lastModDay = tempLastModDate & 0x1F
        tempLastModDate >>= 5
        lastModMonth = tempLastModDate & 0xF
        tempLastModDate >>= 4
        lastModYear = 1980 + (tempLastModDate & 0x7F)
        self.lastModDate = '{}-{:02}-{:02}'.format(
                lastModYear, lastModMonth, lastModDay)


    def _parse(self):
        if self.isEnd():
            return
        if self.isDeleted():
            return

        de = self.data
        self.name = de[0:8].decode('ascii')
        self.ext = de[8:11].decode('ascii')
        self.attr = de[0x0B]
        self._parseLastModTime(de)
        self._parseLastModDate(de)
        self.cluster = struct.unpack('<H', de[0x1A:0x1C])[0]
        self.size = struct.unpack('<I', de[0x1C:0x20])[0]

    def toString(self):
        return "\t{0} {1}\t{2}\t{3} {4}\t{5}".format(
            self.name,
            self.ext,
            self.size,
            self.lastModDate,
            self.lastModTime,
            self.cluster
            )

class FatChain:
    def __init__(self, fat, start):
        self.fat = fat
        self.start = start
        self.current = start

    def isEnd(self):
        return self.current >= 0xFF8

    def next(self):
        i = self.current
        bi = int(i* 12 / 8)
        w = struct.unpack('<H', self.fat[bi:bi+2])[0]
        if (i % 2 == 0):
            self.current =  w & 0xFFF
        else:
            self.current = (w >> 4) & 0xFFF


class Fat12Floppy:
    # sector size
    SECTOR_SIZE = 512
    # directory entry size
    DIR_ENTRY_SIZE = 32

    def __init__(self, imageFileName):
        self.imageFileName = imageFileName
        with open(imageFileName, "rb") as f:
            self.imageData = f.read()
        self.__parse()

    def __parse(self):
        data = self.imageData
        self.bootable = struct.unpack('<H', data[510:512])[0] == 0xaa55

        self.totalSectors = struct.unpack('<H', data[0x13:0x13+2])[0]
        self.numSectorsReserved = struct.unpack('<H', data[0xE:0xE+2])[0]
        self.numSectorsPerCluster = data[0xD]
        self.clusterSize = self.numSectorsPerCluster * self.SECTOR_SIZE
        self.numFat = data[0x10]
        self.numSectorsPerFat = struct.unpack('<H', data[0x16:0x16 + 2])[0]

        self.endOfReserved = self.numSectorsReserved * self.SECTOR_SIZE
        self.endOfFirstFat = self.endOfReserved + \
                self.numSectorsPerFat * self.SECTOR_SIZE
        self.endOfFat = self.endOfReserved + \
                self.numFat * self.numSectorsPerFat * self.SECTOR_SIZE

        numRootDirEntries = struct.unpack('<H', data[0x11:0x11+2])[0];
        self.endOfRootDir = self.endOfFat + \
                numRootDirEntries * self.DIR_ENTRY_SIZE

    def makeBootable(self, yes):
        image = bytearray(self.imageData)
        if yes:
            image[510:512] = [0x55, 0xaa]
        else:
            image[510:512] = [0x00, 0x00]
        self.imageData = bytes(image)
            
    def info(self):
        print(self.imageFileName)
        print("Reserved: 0-{}".format(
            self.endOfReserved / self.SECTOR_SIZE))
        print("FAT: {}-{}".format(
            self.endOfReserved / self.SECTOR_SIZE,
            self.endOfFat / self.SECTOR_SIZE))
        print("Root Directory: {}-{}".format(
            self.endOfFat / self.SECTOR_SIZE,
            self.endOfRootDir / self.SECTOR_SIZE))
        print("Data: {}-{}".format(
            self.endOfRootDir / self.SECTOR_SIZE,
            self.totalSectors))

    def list(self):
        rootDir = self.imageData[self.endOfFat:self.endOfRootDir]
        sizeOfDirEntry = self.DIR_ENTRY_SIZE;
        startOfNextDirEntry = 0
        while True:
            endOfNextDirEntry = startOfNextDirEntry + sizeOfDirEntry
            theDirEntry = rootDir[startOfNextDirEntry:endOfNextDirEntry] 
            startOfNextDirEntry = endOfNextDirEntry

            de = DirectoryEntry(theDirEntry)
            if de.isEnd():
                break
            if de.isDeleted():
                continue
            if de.isDiskLabel():
                continue
            print(de.toString())

    def searchRootDirEntry(self, fileName):
        rootDir = self.imageData[self.endOfFat:self.endOfRootDir]
        sizeOfDirEntry = self.DIR_ENTRY_SIZE;
        startOfNextDirEntry = 0
        while True:
            endOfNextDirEntry = startOfNextDirEntry + sizeOfDirEntry
            theDirEntry = rootDir[startOfNextDirEntry:endOfNextDirEntry] 
            startOfNextDirEntry = endOfNextDirEntry

            de = DirectoryEntry(theDirEntry)
            if de.isEnd():
                break
            if de.isDeleted():
                continue
            if de.isDiskLabel():
                continue
            if de.fullName() == fileName:
                return de
        return None

    def searchRootDirEntryIndex(self, fileName):
        image = self.imageData
        sizeOfDirEntry = self.DIR_ENTRY_SIZE;
        index = self.endOfFat - sizeOfDirEntry
        while True:
            index += sizeOfDirEntry
            theDirEntry = image[index:index + sizeOfDirEntry] 

            de = DirectoryEntry(theDirEntry)
            if de.isEnd():
                break
            if de.isDeleted():
                continue
            if de.isDiskLabel():
                continue
            if de.fullName() == fileName:
                return index
        return None

    def findAvailableRootDirEntryIndex(self):
        image = self.imageData
        sizeOfDirEntry = self.DIR_ENTRY_SIZE;
        index = self.endOfFat - sizeOfDirEntry
        while index < self.endOfRootDir:
            index += sizeOfDirEntry
            theDirEntry = image[index:index + sizeOfDirEntry] 

            de = DirectoryEntry(theDirEntry)
            if de.isDeleted() or de.isEnd():
                return index
        return None

    def getFileContent(self, fileName):
        fileName  = fileName.upper()
        fat = self.imageData[self.endOfReserved:self.endOfFirstFat]
        dataRegion = self.imageData[self.endOfRootDir:]

        de = self.searchRootDirEntry(fileName)
        if de == None:
            return None
        chain = FatChain(fat, de.cluster)
        fileContent = bytes()
        while not chain.isEnd():
            start = (chain.current - 2) * self.clusterSize
            end = start + self.clusterSize
            fileContent += dataRegion[start:end]
            chain.next()
        return fileContent[0:de.size]

    def makeDirEntry(fileName, cluster, size):
        otherField = bytes.fromhex('00') * 11
        fileName = fileName.upper()
        dotIndex = fileName.index('.')
        # name
        name = fileName[0:dotIndex]
        nameField = bytearray(' '*8, 'ascii')
        nameField[0:len(name)] = name.encode('ascii')
        # ext
        ext = fileName[dotIndex+1:]
        extField = bytearray(' '*3, 'ascii')
        extField[0:len(ext)] = ext.encode('ascii')

        now = datetime.datetime.now()
        # last modification time
        lmtField = ((now.hour & 0x1F) << 11) |\
                ((now.minute & 0x3F) << 5) |\
                (int(now.second / 2) & 0x1F)
        # last modification date
        lmdField = (((now.year - 1980) & 0x7F) << 9) |\
                ((now.month & 0xF) << 5) |\
                (now.day & 0x1F)

        return nameField + extField +\
            otherField +\
            struct.pack('<H', lmtField) +\
            struct.pack('<H', lmdField) +\
            struct.pack('<H', cluster) +\
            struct.pack('<I', size)
        
    def insertFile(self, fileName, content):
        newImageData = bytearray(self.imageData)
        dirEntry = self.searchRootDirEntry(fileName)
        if dirEntry != None:
            raise Exception(fileName + ' exists')
        # create fat and data
        contentLen = len(content)
        if contentLen == 0:
            startCluster = 0
        else:
            dataPos = 0
            startCluster = self._findAvailableCluster(newImageData)
            if startCluster == None:
                raise Exception("Out of disk space")
            # use it, not available
            self._writeFatEntry(newImageData, startCluster, 0xFFF)
            currentCluster = startCluster
            # write first cluster
            dataLenToWrite = min(self.clusterSize, contentLen - dataPos)
            dataToWrite = content[dataPos:dataPos + dataLenToWrite]
            self._writeData(newImageData, currentCluster, dataToWrite)
            dataPos += dataLenToWrite
            # write rest cluster
            while dataPos < contentLen:
                nextCluster = self._findAvailableCluster(newImageData)
                if nextCluster == None:
                    raise Exception("Out of disk space")
                self._writeFatEntry(newImageData, nextCluster, 0xFFF)
                # write data
                dataLenToWrite = min(self.clusterSize, contentLen - dataPos)
                dataToWrite = content[dataPos:dataPos + dataLenToWrite]
                self._writeData(newImageData, nextCluster, dataToWrite)
                dataPos += dataLenToWrite
                # write fat entry
                self._writeFatEntry(newImageData, currentCluster, nextCluster)
                currentCluster = nextCluster
        # create dir entry
        dirEntry = Fat12Floppy.makeDirEntry(fileName, 
                startCluster, len(content))
        dirEntryIndex = self.findAvailableRootDirEntryIndex()
        newImageData[dirEntryIndex:dirEntryIndex+32] = dirEntry

        self.imageData = bytes(newImageData)
        return True

    def deleteFile(self, fileName):
        newImageData = bytearray(self.imageData)

        fat = self.imageData[self.endOfReserved:self.endOfFirstFat]
        deIndex = self.searchRootDirEntryIndex(fileName)
        if deIndex == None:
            return False
        de = DirectoryEntry(newImageData[deIndex:deIndex+32]) 
        chain = FatChain(fat, de.cluster)
        while not chain.isEnd():
            self._writeFatEntry(newImageData, chain.current, 0)
            chain.next()
       
        newImageData[deIndex] = 0xE5
        self.imageData = bytes(newImageData)
        return True

    def _writeData(self, image, cluster, data):
        dataIndex = self.endOfRootDir + (cluster - 2) * self.clusterSize
        image[dataIndex:dataIndex + len(data)] = data

    def _writeFatEntry(self, data, n, v):
        for i in range(self.numFat):
            startOfCurrentFat = self.endOfReserved + \
                    i * self.numSectorsPerFat * self.SECTOR_SIZE
            byteIndex = int(n * 12 / 8) + startOfCurrentFat
            origValue = struct.unpack('<H', data[byteIndex:byteIndex+2])[0]
            if n % 2 == 0:
                newValue = (origValue & 0xF000) + v
            else:
                newValue = (origValue & 0xF) + (v << 4)
            data[byteIndex] = newValue & 0xFF
            data[byteIndex+1] = (newValue >> 8) & 0xFF

    def _findAvailableCluster(self, image):
        startOfFirstFat = self.endOfReserved
        endOfFirstFat = startOfFirstFat + \
                self.numSectorsPerFat * self.SECTOR_SIZE
        i = startOfFirstFat + 3
        n = 2
        while i < endOfFirstFat:
            ent = struct.unpack('<H', image[i:i+2])[0]
            if ent & 0xFFF == 0:
                return n
            ent = struct.unpack('<H', image[i+1:i+3])[0]
            if ent & 0xFFF0 == 0:
                return n + 1
            i += 3
            n += 2
        return None
            

    def saveImage(self, newImageFileName):
        with open(newImageFileName, "wb") as f:
            f.write(self.imageData)
        

        

def usage():
    print("""usage:
    python3 fat12floppy.py <image>
""")
    sys.exit(1)

if __name__ == "__main__":
    print("fat12floppy v0.01")
    argv = sys.argv
    argv.pop(0)
    if len(argv) < 1:
        usage();

    # read file whole content
    imageFileName = argv.pop(0)
    floppy = Fat12Floppy(imageFileName)
    #floppy.info()
    #floppy.list()

    fileName = argv.pop(0)
    #de = floppy.searchRootDirEntry(fileName)
    #if None != de:
    #    print("Found: " + de.toString())
    #    print("Coutent:")
    #    print(floppy.getFileContent(fileName))
    #else:
    #    print("Not found")

    #floppy.deleteFile(fileName)
    #floppy.list()
    #print(floppy.getFileContent(fileName))
    #print(Fat12Floppy.makeDirEntry('asdb.123', 2, 100))
    #floppy.list()
    content = b'1234567890abcdefghijklmnopqrstuvwxyz\r\n' * 40
    floppy.deleteFile('ABCDEF.TXT')
    floppy.insertFile('ABCDEF.TXT', content)
    print("After insertFile")
    floppy.list()
    print(floppy.getFileContent(fileName))
    floppy.makeBootable(False)
    #print(floppy.bootable)
    floppy.saveImage("bak.img")
