# fake mkzopeinstance, that creates a minimal
# structure for the recipe to get happy
import sys
import os

def _mkdir(d):
    if not os.path.exists(d):
        os.makedirs(d)

try:
    dir_ = sys.argv[-3]
except:
    dir_ = sys.argv[-1]

_mkdir(dir_)
_mkdir(os.path.join(dir_, 'etc'))
_mkdir(os.path.join(dir_, 'bin'))

for file_ in ('runzope', 'zopectl', 'runzope.bat', 'zopeservice.py'):
    f = open(os.path.join(dir_, 'bin', file_), 'w')
    f.write("#")
    f.close()

