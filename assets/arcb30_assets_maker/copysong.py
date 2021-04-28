import shutil
import os
import re

path = os.path.abspath('./songs')
dirs = os.listdir(path)

for file in dirs:
    filename = os.path.abspath(f'{path}/{file}')
    if os.path.isdir(filename):
        output = os.path.abspath('./output/')
        if not os.path.exists(output):
            os.makedirs(output)
        file = re.sub('dl_','',file)
        filename = filename+'/base.jpg'
        if os.path.exists(filename):
            shutil.copy(filename,f'{output}/{file}.jpg')
