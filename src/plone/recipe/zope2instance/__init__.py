##############################################################################
#
# Copyright (c) 2006-2007 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

import os, re, shutil
import zc.buildout
import zc.recipe.egg
from stat import S_IRWXG, S_IRWXU, S_ISGID

SUPERVISE_PERMS =  S_IRWXU|S_IRWXG|S_ISGID
SCRIPT_PERMS =  S_IRWXU|S_IRWXG

class Recipe:

    def __init__(self, buildout, name, options):
        self.egg = zc.recipe.egg.Egg(buildout, options['recipe'], options)
        self.buildout, self.options, self.name = buildout, options, name

        options['location'] = os.path.join(
            buildout['buildout']['parts-directory'],
            self.name,
            )
        options['bin-directory'] = buildout['buildout']['bin-directory']
        options['scripts'] = '' # suppress script generation.

    def install(self):
        options = self.options
        location = options['location']

        requirements, ws = self.egg.working_set()
        ws_locations = [d.location for d in ws]

        if os.path.exists(location):
            shutil.rmtree(location)

        # What follows is a bit of a hack because the instance-setup mechanism
        # is a bit monolithic. We'll run mkzopeinstance and then we'll
        # patch the result. A better approach might be to provide independent
        # instance-creation logic, but this raises lots of issues that
        # need to be stored out first.
        mkzopeinstance = os.path.join(options['zope2-location'],
                                      'utilities', 'mkzopeinstance.py')

        assert os.spawnl(
            os.P_WAIT, options['executable'], options['executable'],
            mkzopeinstance, '-d', location, '-u', options['user'],
            ) == 0

        try:
            # Save the working set:
            open(os.path.join(location, 'etc', '.eggs'), 'w').write(
                '\n'.join(ws_locations))

            # create daemontools structure
            self.create_daemontools_structure()

            # Make a new zope.conf based on options in buildout.cfg
            self.build_zope_conf()
            
            # Patch extra paths into binaries
            self.patch_binaries(ws_locations)

            # Install extra scripts
            self.install_scripts(ws_locations)

            # Add zcml files to package-includes
            self.build_package_includes()
        except:
            # clean up
            shutil.rmtree(location)
            raise

        return location

    def update(self):
        options = self.options
        location = options['location']

        requirements, ws = self.egg.working_set()
        ws_locations = [d.location for d in ws]

        if os.path.exists(location):
            # See is we can stop. We need to see if the working set path
            # has changed.
            saved_path = os.path.join(location, 'etc', '.eggs')
            if os.path.isfile(saved_path):
                if (open(saved_path).read() !=
                    '\n'.join(ws_locations)
                    ):
                    # Something has changed. Blow away the instance.
                    self.install()

            # Nothing has changed.
            return location

        else:
            self.install()

        return location

    def create_daemontools_structure(self):
        options = self.options
        location = options['location']

        supervise_dir = os.path.join(location,'supervise')
        log_supervise_dir = os.path.join(location,'log','supervise')
        log_main_dir = os.path.join(location,'log','main')

        # create daemontools structure
        os.mkdir(supervise_dir)
        os.mkdir(log_supervise_dir)
        os.mkdir(log_main_dir)

        # make sure daemontools' control files are owned by zope
        os.chmod(supervise_dir, SUPERVISE_PERMS)
        os.chmod(log_supervise_dir, SUPERVISE_PERMS)

    def build_zope_conf(self):
        """Create a zope.conf file
        """
        
        options = self.options
        location = options['location']
        
        products = options.get('products', '')
        if products:
            products = products.split('\n')
            # Filter out empty directories
            products = [p for p in products if p]
            # Make sure we have consistent path seperators
            products = [os.path.abspath(p) for p in products]
        
        instance_home = location
        products_lines = '\n'.join(['products %s' % p for p in products])
        debug_mode = options.get('debug-mode', 'off')
        security_implementation = 'C'
        verbose_security = options.get('verbose-security', 'off')
        if verbose_security == 'on':
            security_implementation = 'python'
        http_address = options.get('http-address', '8080')
        zope_conf_additional = options.get('zope-conf-additional', '')
        
        base_dir = self.buildout['buildout']['directory']
        
        event_log_name = options.get('event-log', os.path.sep.join(('var', 'log', 'event.log',)))
        event_log = os.path.join(base_dir, event_log_name)
        event_log_dir = os.path.dirname(event_log)
        if not os.path.exists(event_log_dir):
            os.makedirs(event_log_dir)
            
        z_log_name = options.get('z-log', os.path.sep.join(('var', 'log', 'Z2.log',)))
        z_log = os.path.join(base_dir, z_log_name)
        z_log_dir = os.path.dirname(z_log)
        if not os.path.exists(z_log_dir):
            os.makedirs(z_log_dir)
            
        file_storage = options.get('file-storage', os.path.sep.join(('var', 'filestorage', 'Data.fs',)))
        file_storage = os.path.join(base_dir, file_storage)
        file_storage_dir = os.path.dirname(file_storage)
        if not os.path.exists(file_storage_dir):
            os.makedirs(file_storage_dir)

        zeo_client = options.get('zeo-client', '')
        zeo_address = options.get('zeo-address', '8100')
        zeo_dbs=''
        
        if zeo_client.lower() in ('yes', 'true', 'on', '1'):
            template = zeo_conf_template
            dbs = options.get('dbs',None)
            if dbs:
                dbs = dbs.split('\n')
                for db in dbs:
                    zeo_dbs += zeo_db_template % (dict(
                            db_name=db,
                            zeo_address=zeo_address,
                            instance_home=instance_home
                        ))
        else:
            template = zope_conf_template
            
        zope_conf = template % dict(instance_home = instance_home,
                                    products_lines = products_lines,
                                    debug_mode = debug_mode,
                                    security_implementation = security_implementation,
                                    verbose_security = verbose_security,
                                    event_log = event_log,
                                    z_log = z_log,
                                    file_storage = file_storage,
                                    http_address = http_address,
                                    zeo_address=zeo_address,
                                    zeo_dbs=zeo_dbs,
                                    zope_conf_additional = zope_conf_additional,)
        
        zope_conf_path = os.path.join(location, 'etc', 'zope.conf')
        open(zope_conf_path, 'w').write(zope_conf)
        
    def patch_binaries(self, ws_locations):
        location = self.options['location']
        # XXX We need to patch the windows specific batch scripts
        # and they need a different path seperator
        path =":".join(ws_locations)
        for script_name in ('runzope', 'zopectl'):
            script_path = os.path.join(location, 'bin', script_name)
            script = open(script_path).read()
            script = script.replace(
                '$SOFTWARE_HOME:$PYTHONPATH',
                '$SOFTWARE_HOME:'+path+':$PYTHONPATH'
                )
            f = open(script_path, 'w')
            f.write(script)
            f.close()
        # Patch Windows scripts
        path =";".join(ws_locations)
        for script_name in ('runzope.bat', ):
            script_path = os.path.join(location, 'bin', script_name)
            script = open(script_path).read()
            # This could need some regex-fu
            lines = [l for l in script.splitlines() if not l.startswith('@set PYTHON=')]
            lines.insert(2, '@set PYTHON=%s' % self.options['executable'])
            script = '\n'.join(lines)
            script = script.replace(
                'PYTHONPATH=%SOFTWARE_HOME%',
                'PYTHONPATH=%SOFTWARE_HOME%;'+path+';%PYTHONPATH%'
                )
            f = open(script_path, 'w')
            f.write(script)
            f.close()
        # Add a test.bat that works on Windows
        new_script_path = os.path.join(location, 'bin', 'test.bat')
        script_path = os.path.join(location, 'bin', 'runzope.bat')
        script = open(script_path).read()
        # Adjust script to use the right command
        script = script.replace("@set ZOPE_RUN=%SOFTWARE_HOME%\\Zope2\\Startup\\run.py", 
                                """@set ZOPE_RUN=%ZOPE_HOME%\\test.py
@set ERRLEV=0""")
        script = script.replace("\"%ZOPE_RUN%\" -C \"%CONFIG_FILE%\" %1 %2 %3 %4 %5 %6 %7",
                                """\"%ZOPE_RUN%\" --config-file \"%CONFIG_FILE%\" %1 %2 %3 %4 %5 %6 %7 %8 %9
@IF %ERRORLEVEL% NEQ 0 SET ERRLEV=1
@ECHO \"%ERRLEV%\">%INSTANCE_HOME%\\testsexitcode.err""")
        f = open(new_script_path, 'w')
        f.write(script)
        f.close()

    def install_scripts(self, ws_locations):
        options = self.options
        location = options['location']
        
        zope_conf_path = os.path.join(location, 'etc', 'zope.conf')
        extra_paths = [os.path.join(location),
                       os.path.join(options['zope2-location'], 'lib', 'python')
                      ]
        extra_paths.extend(ws_locations)
        
        requirements, ws = self.egg.working_set(['plone.recipe.zope2instance'])

        zc.buildout.easy_install.scripts(
            [(self.name, 'plone.recipe.zope2instance.ctl', 'main')],
            ws, options['executable'], options['bin-directory'],
            extra_paths = extra_paths,
            arguments = ('\n        ["-C", %r]'
                         '\n        + sys.argv[1:]'
                         % zope_conf_path
                         ),
            )

        run_script = daemontools_run_template % options

        run_script_path = os.path.join(location, 'run')
        open(run_script_path, 'w').write(run_script)
        os.chmod(run_script_path, SCRIPT_PERMS)

        log_run_script = daemontools_log_run_template % options

        log_run_script_path = os.path.join(location, 'log', 'run')
        open(log_run_script_path, 'w').write(log_run_script)
        os.chmod(log_run_script_path, SCRIPT_PERMS)

        if not options['zeo-client']:
  
          repozo_script = repozo_script_template % options
  
          repozo_script_path = os.path.join(location, 'bin', 'repozo')
          open(repozo_script_path, 'w').write(repozo_script)
          os.chmod(repozo_script_path, SCRIPT_PERMS)

          ctlscript = "%s/%s" % (bindir, repozo)
          os.symlink("%s/bin/repozo" % location, ctlscript)

    def build_package_includes(self):
        """Create ZCML slugs in etc/package-includes
        """
        
        location = self.options['location']
        zcml = self.options.get('zcml')
        
        if zcml:
            sitezcml_path = os.path.join(location, 'etc', 'site.zcml')
            if not os.path.exists(sitezcml_path):
                # Zope 2.9 does not have a site.zcml so we copy the
                # one out from Five.
                zope2_location = self.options['zope2-location']
                skel_path = os.path.join(zope2_location, 'lib', 'python',
                                         'Products', 'Five', 'skel',
                                         'site.zcml')
                shutil.copyfile(skel_path, sitezcml_path)

            includes_path = os.path.join(location, 'etc', 'package-includes')
            if not os.path.exists(includes_path):
                # Zope 2.9 does not have a package-includes so we
                # create one.
                os.mkdir(includes_path)

            zcml = zcml.split()
            if '*' in zcml:
                zcml.remove('*')
            else:
                shutil.rmtree(includes_path)
                os.mkdir(includes_path)

            n = 0
            package_match = re.compile('\w+([.]\w+)*$').match
            for package in zcml:
                n += 1
                orig = package
                if ':' in package:
                    package, filename = package.split(':')
                else:
                    filename = None

                if '-' in package:
                    package, suff = package.split('-')
                    if suff not in ('configure', 'meta', 'overrides'):
                        raise ValueError('Invalid zcml', orig)
                else:
                    suff = 'configure'

                if filename is None:
                    filename = suff + '.zcml'

                if not package_match(package):
                    raise ValueError('Invalid zcml', orig)

                path = os.path.join(
                    includes_path,
                    "%3.3d-%s-%s.zcml" % (n, package, suff),
                    )
                open(path, 'w').write(
                    '<include package="%s" file="%s" />\n'
                    % (package, filename)
                    )

# The template used to build zope.conf
zope_conf_template="""\
instancehome %(instance_home)s
%(products_lines)s
debug-mode %(debug_mode)s
security-policy-implementation %(security_implementation)s
verbose-security %(verbose_security)s

<eventlog>
  level info
  <logfile>
    path %(event_log)s
    level info
  </logfile>
</eventlog>

<logger access>
  level WARN
  <logfile>
    path %(z_log)s
    format %%(message)s
  </logfile>
</logger>

<http-server>
  # valid keys are "address" and "force-connection-close"
  address %(http_address)s
  # force-connection-close on
  # You can also use the WSGI interface between ZServer and ZPublisher:
  # use-wsgi on
</http-server>

<zodb_db main>
    # Main FileStorage database
    <filestorage>
      path %(file_storage)s
    </filestorage>
    mount-point /
</zodb_db>

<zodb_db temporary>
    # Temporary storage database (for sessions)
    <temporarystorage>
      name temporary storage for sessioning
    </temporarystorage>
    mount-point /temp_folder
    container-class Products.TemporaryFolder.TemporaryContainer
</zodb_db>

%(zope_conf_additional)s
"""

zeo_db_template = """\
<zodb_db %(db_name)s>
  mount-point /%(db_name)s
  <zeoclient>
    server %(zeo_address)s
    storage %(db_name)s
    name zeostorage
    var %(instance_home)s/var
  </zeoclient>
</zodb_db>
"""

zeo_conf_template="""\
instancehome %(instance_home)s
%(products_lines)s
debug-mode %(debug_mode)s
security-policy-implementation %(security_implementation)s
verbose-security %(verbose_security)s

<eventlog>
  level info
  <logfile>
    path %(event_log)s
    level info
  </logfile>
</eventlog>

<logger access>
  level WARN
  <logfile>
    path %(z_log)s
    format %%(message)s
  </logfile>
</logger>

<http-server>
  # valid keys are "address" and "force-connection-close"
  address %(http_address)s
  # force-connection-close on
  # You can also use the WSGI interface between ZServer and ZPublisher:
  # use-wsgi on
</http-server>

<zodb_db main>
  mount-point /
  <zeoclient>
    server %(zeo_address)s
    storage 1
    name zeostorage
    var %(instance_home)s/var
  </zeoclient>
</zodb_db>

<zodb_db temporary>
    # Temporary storage database (for sessions)
    <temporarystorage>
      name temporary storage for sessioning
    </temporarystorage>
    mount-point /temp_folder
    container-class Products.TemporaryFolder.TemporaryContainer
</zodb_db>

%(zeo_dbs)s

%(zope_conf_additional)s
"""

daemontools_run_template="""\
#! /bin/sh
#
# run script for zope under djb daemontools
#

exec 2>&1

PYTHON="%(bin-directory)s/zopepy"
ZOPE_HOME="%(zope2-location)s"
INSTANCE_HOME="%(location)s"
CONFIG_FILE="$INSTANCE_HOME/etc/zope.conf"
SOFTWARE_HOME="$ZOPE_HOME/lib/python"
PYTHONPATH="$SOFTWARE_HOME"
export PYTHONPATH INSTANCE_HOME SOFTWARE_HOME

ZOPE_RUN="$SOFTWARE_HOME/Zope2/Startup/run.py"

exec /command/setuidgid zope "$PYTHON" "$ZOPE_RUN" -C "$CONFIG_FILE" "$@"
"""

daemontools_log_run_template="""\
#!/bin/sh
exec /command/setuidgid zope /usr/local/bin/multilog t ./main
"""

repozo_script_template="""\
#! /bin/sh
#
# run script for zope under djb daemontools
#

exec 2>&1

PYTHON="%(bin-directory)s/zopepy"
ZOPE_HOME="%(zope2-location)s"
INSTANCE_HOME="%(location)s"
CONFIG_FILE="$INSTANCE_HOME/etc/zope.conf"
SOFTWARE_HOME="$ZOPE_HOME/lib/python"
PYTHONPATH="$SOFTWARE_HOME"
export PYTHONPATH INSTANCE_HOME SOFTWARE_HOME

REPOZO="$ZOPE_HOME/bin/repozo.py"

exec /command/setuidgid zope "$PYTHON" "$REPOZO" -C "$CONFIG_FILE" "$@"
"""
