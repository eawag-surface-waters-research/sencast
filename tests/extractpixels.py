from postprocess.pixelextraction.pixelextration import pixelextration
import os

def getListOfFiles(dirName):
    # create a list of file and sub directories
    # names in the given directory
    listOfFile = os.listdir(dirName)
    allFiles = list()
    # Iterate over all the entries
    for entry in listOfFile:
        # Create full path
        fullPath = os.path.join(dirName, entry)
        # If entry is a directory then get the list of files in this directory
        if os.path.isdir(fullPath):
            allFiles = allFiles + getListOfFiles(fullPath)
        else:
            allFiles.append(fullPath)

    return allFiles


def filterFiles(files, string):
    return [file for file in files if string in file]


folder = "/media/jamesrunnalls/JamesSSD/Eawag/EawagRS/Sencast"
coords = [{"name": "A", "lat": 46.44829, "lng": 6.561426}]
files = getListOfFiles("/media/jamesrunnalls/JamesSSD/Eawag/EawagRS/Sencast/build/DIAS/output_data/datalakes_sui_S3_sui_2018-06-01_2018-06-07")
files = filterFiles(files, "L2PP_")

pixelextration(files, coords, folder)
