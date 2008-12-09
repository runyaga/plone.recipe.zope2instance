# fake mkzopeinstance, that creates a minimal
# structure for the recipe to get happy
import sys
import os

def _mkdir(d):
    if not os.path.exists(d):
        os.mkdir(d)

if len(sys.argv) == 5:
    # <prog> -d <dirname> -u <user:password>
    dir_ = sys.argv[-3]
elif len(sys.argv) == 3:
    # <prog> -d <dirname>
    dir_ = sys.argv[-1]
else:
    raise RuntimeError('Unknown number of cmdline arguments')

_mkdir(dir_)
_mkdir(os.path.join(dir_, 'etc'))
_mkdir(os.path.join(dir_, 'bin'))

for file_ in ('runzope', 'zopectl', 'runzope.bat', 'zopeservice.py'):
    f = open(os.path.join(dir_, 'bin', file_), 'w')
    f.write("#")
    f.close()

