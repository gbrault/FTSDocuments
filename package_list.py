import pkgutil
import os

def get_py_files(directory):
    py_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))
    return py_files

def list_python_files(package_name):
    package = __import__(package_name)
    path = package.__path__
    files = get_py_files(path[0])
    for i,file in enumerate(files):
        files[i] = file.replace(path[0] + os.sep, '')
    return files

for file in list_python_files("flask_appbuilder"):
    print(file)