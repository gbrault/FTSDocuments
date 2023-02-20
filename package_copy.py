import pkgutil
import os

def get_py_files(directory):
    py_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            py_files.append(os.path.join(root, file))
    return py_files

def list_python_files(package_name):
    package = __import__(package_name)
    path = package.__path__
    files = get_py_files(path[0])
    return path[0],package.__name__, files

package_name = "flask_appbuilder"
path,package, files = list_python_files(package_name)
for file in files:
    with open(file, "rb") as f:
        template = f.read()
    file_ = file.replace(path,"")[1:]
    filepath = os.path.abspath(os.path.join(os.getcwd(),package_name,file_))
    basedir = os.path.dirname(filepath)
    os.makedirs(basedir, exist_ok=True)
    with open(os.path.join(package_name,file_), "wb") as f:
        f.write(template)