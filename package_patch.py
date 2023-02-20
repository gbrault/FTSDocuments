import argparse
import pkgutil
import os
import shutil
import json

def get_files(directory):
    py_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if '__pycache__' in root:
                continue
            py_files.append(os.path.join(root, file))
    return py_files

def list_python_files(package_name):
    package = __import__(package_name)
    path = package.__path__
    files = get_files(path[0])
    return path[0],package.__name__, files

def patch_package(package_name):
    # erase package directory if exists
    if os.path.exists(package_name):
        shutil.rmtree(package_name)
    # read the patch_{package_name}.json file in patch_{package_name} directory
    # and copy the files to the package directory
    with open(os.path.join("patch_"+package_name,"patch_"+package_name+".json")) as f:
        patch = json.load(f)
    path,package, files = list_python_files(package_name)
    for file in files:
        with open(file, "rb") as f:
            template = f.read()
        file_ = file.replace(path,"")[1:]
        filepath = os.path.abspath(os.path.join(os.getcwd(),package_name,file_))
        basedir = os.path.dirname(filepath)
        os.makedirs(basedir, exist_ok=True)
        with open(os.path.join(package_name,file_), "wb") as f:
            cfile_ = file_.replace(os.path.sep,"/")
            directives = None
            for file in patch['patches']:
                if file['file'] == cfile_:
                    directives = file
            if directives is not None:
                if file_.endswith(".py"):
                    if directives["kind"] == "replace":
                        for patching in patch['py'][cfile_]:
                            template = template.replace(patching['original'].encode(), patching['patched'].encode())
                        f.write(template)
                    elif directives["kind"] == "shadow":    
                        # copy the patch file
                        with open(os.path.join("patch_"+package_name,package_name,file_), "rb") as f2:
                            template2 = f2.read()
                        f.write(template2)
                        # copy the original file and rename it original_{file}
                        newbasefile = os.path.join(os.path.dirname(file_),"original_"+os.path.basename(file_))
                        with open(os.path.join(package_name,newbasefile), "wb") as f3:
                            f3.write(template)
                elif file_.endswith('.js'):
                    # read patch['js']['{file}'] and replace the content
                    for patching in patch['js'][cfile_]:
                        template = template.replace(patching['original'].encode(), patching['patched'].encode())
                    f.write(template)
            else:
                # just copy the original file
                f.write(template)

# main
if __name__ == "__main__":
    # reads args
    parser = argparse.ArgumentParser(description='Package patcher')
    parser.add_argument('--package', type=str, help='package name')
    args = parser.parse_args()
    package_name = args.package
    patch_package(package_name)
