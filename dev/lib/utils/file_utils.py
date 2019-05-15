# module containing methods for file handling
import os


def filehandle_for(filename):
    if filename == "-":
        filehandle = sys.stdin
    else:
        filehandle = open(filename)
    return filehandle


def list_files_in_dir(path, extension='*'):
    files = []
    for root, _, files in os.walk(path):
        for file in files:
            if extension in file:
                files.append(os.path.join(root, file))
    return files


