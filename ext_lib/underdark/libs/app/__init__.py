#!/usr/bin/python2.5
"""Framework for Python applications.

Sets up logging and other future shinies before calling the main() function
from the calling module.
"""
__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.5'

# Standard modules
import ConfigParser
import os
import shutil
import signal
import sys
import warnings

# Package modules
from .daemon import runner
from . import logging
from .logging import extras
from .logging import handlers

WARNING_SQLITE_NODATABASE = """
  SQLTalk (SQLite) returned an Operational Error when trying to open the
  following database file: %r.
  The application be logging to stderr, NOT to the expected database.
"""

LOCKFILE_PATHS = (
    '/var/lock/underdark/%s',
    os.path.expanduser('~/.underdark/%s/lock/'))
LOGGING_PATHS = (
    '/var/log/underdark/%s/',
    os.path.expanduser('~/.underdark/%s/logs/'))
CONFIG_READ_PATHS = (
    '/etc/underdark/%s/',
    os.path.expanduser('~/.underdark/%s/config/'))
CONFIG_WRITE_PATH = os.path.expanduser('~/.underdark/%s/config/')


class Application(object):
  """Container for an application, allows setup of logging and misc I/O streams.

  Based on a passed in `application_frame`, the application is set up with a
  module name and default logging, config and lockfile paths (whichever apply).

  The given frame *must* be that of the __main__ of a module, and the function
  that is called on Run() of this class, is *always* the main() of __main__.

  Clients usually won't need to create their own Application object, the module
  level functions Daemon(), Run() and Service() should be used instead.
  These will pass along any named options and set up the Application from the
  correct frame.

  Methods:
    @ Run
      Sets up logging and runs the application for this instance.
    @ _ProcessConfig
      Builds configuration from multiple configuration file locations.
  """
  def __init__(self, application_frame, **options):
    """Initializes a new Application from the given `caller_frame` and `options.

    Based on the given frame, the applications `module` name and its
    `local_path` are determined, which are used for naming various files
    described below (the `local_path` is used for retrieving the config file).

    Arguments:
      @ application_frame: frame
        The frame that the application's main() function lives in.
        Additionally, this frame needs to have a name `__main__` and has to
        have a `__file__` attribute. (No calling from live interpreter.)
      % config_file: str ~~ None
        Name of the config file to use for this application. The given file is
        searched on the `config_read_paths`, and local_path if this fails.
        See the documentation for ProcessConfig() for more information.
      % daemon: boolean ~~ False
        Flag whether the application should be set up as a daemon. Setting this
        causes instance attributes `stdin_path`, `stderr_path`, `stdout_path`,
        `pidfile_path` and `pidfile_timeout` to be set.
      % package: str ~~ application_frame's module name
        An alternative name to use for logging, config and pidfile paths.
        This allows multiple related modules to have their files grouped.
      % config_read_paths: iterable ~~ CONFIG_READ_PATHS
        Paths config files should be read from. Each path should contain one
        string replacement position for the `package` argument.
      % config_write_path: str ~~ CONFIG_WRITE_PATH
        Path to copy config to if it only exists on the application's own path.
      % lockfile_paths: iterable ~~ LOCKFILE_PATHS
        Paths pid- and lockfiles should be written to. This is only relevant if
        `daemon` is flagged True. Each path should contain one string
        replacement position for the `package` argument.
        The first writable directory will be used to create the following files:
          '%(module)s.pid'      - UNIX pidfile containing application pid.
          '%(module)s.pid.lock' - lockfile generated by lockfile module.
      % logging_paths: iterable ~~ LOGGING_PATHS
        Paths logfiles should be written to. Each path should contain one
        string replacement position for the `package` argument.
        The first writable directory will be used to create the following files:
          '%(module)s.sqlite'  - logfile for logging.Log* calls.
          '%(module)s.log'     - if `daemon`, redirects sys.stdout to this file.
          '%(module)s.err.log' - if `daemon`, redirects sys.stderr to this file.
      % stdin_path: str ~~ None
        The path
    """
    if application_frame.f_globals['__name__'] != '__main__':
      print 'Got called from %r' % application_frame.f_globals['__name__']
      raise RuntimeError('This may be called from a module\'s __main__ only.')
    if not application_frame.f_globals.get('__file__'):
      raise RuntimeError(
          'Frame lacks `__file__`. Are you running from the live interpreter?')

    options.setdefault('config_read_paths', CONFIG_READ_PATHS)
    options.setdefault('config_write_path', CONFIG_WRITE_PATH)
    options.setdefault('lockfile_paths', LOCKFILE_PATHS)
    options.setdefault('logging_paths', LOGGING_PATHS)

    if 'app' in options:
      self.app = options['app']
    else:
      self.app = sys.modules['__main__'].main
    self.fullpath = os.path.abspath(application_frame.f_globals['__file__'])
    module = os.path.splitext(os.path.basename(self.fullpath))[0]
    package = options.get('package', module)

    # Stream logging paths for this application
    logging_dir = FirstWritablePath(MakePaths(LOGGING_PATHS, package))
    self.logging_path = os.path.join(logging_dir, '%s.sqlite' % module)

    self.config = {}
    if options.get('config'):
      self.config = ReadConfig(options['config'],
                               local_path=os.path.dirname(self.fullpath),
                               read_paths=MakePaths(CONFIG_READ_PATHS, package),
                               write_path=CONFIG_WRITE_PATH % package)

    if options.get('daemon'):
      # Redirection of default UNIX file descriptors
      self.stdin_path = options.get('stdin_path', os.devnull)
      self.stdout_path = os.path.join(logging_dir, '%s.log' % module)
      self.stderr_path = os.path.join(logging_dir, '%s.err.log' % module)

      # Pidfile path and settings for this application
      lock_paths = FirstWritablePath(MakePaths(LOCKFILE_PATHS, package))
      self.pidfile_path = os.path.join(lock_paths, module + '.pid')
      self.pidfile_timeout = options.get('pidfile_timeout', 0)

      # Optional settings for the daemon to be created from this Application.
      self.chroot_dir = options.get('chroot_path')
      self.working_dir = options.get('working_dir', '/')
      self.umask = options.get('umask', 0002)

  def Run(self):
    """Starts the actual application."""
    def ForcefulTermination(_signum, _frame):
      """Logs a message for the pending forceful termination.

      N.B. This may not always trigger, even though a SIGKILL will be issued.
      The reasons for this are still under investigation.
      """
      #FIXME(Elmer): This SIGALRM handler doesn't seem to run, why?
      logging.LogCritical('Daemon still refusing to quit after 5 seconds. '
                          'Unconditional termination in another 3 seconds.')
      logging.Shutdown()

    SetUpLogging(self.logging_path)
    logging.LogInfo('Application starting; running %r of %r',
                    self.app.__name__, self.fullpath)
    try:
      self.app(**self.config)
      logging.Shutdown()
    except SystemExit:
      sys.stderr.write('\nSystemExit received, halting execution.\n')
      logging.LogInfo('SystemExit received, halting execution.')
      logging.FlushAll()
      signal.signal(signal.SIGALRM, ForcefulTermination)
      signal.alarm(5)
    except Exception:
      logging.LogException('Unhandled error causing application exit.')
      raise


def FirstWritablePath(paths):
  """Given a list of paths, returns the first one that is writable.

  For each given path that does not exist, the function attempts to create it.

  Arguments:
    @ paths: iterable
      Strings that represent paths

  Raises:
    ValueError - if none of the paths are writable

  Returns
    str - the first writable path
  """
  for path in paths:
    if os.path.isdir(path) and os.access(path, os.W_OK):
      return path
    try:
      os.makedirs(path)
      return path
    except OSError:
      continue
  raise ValueError('None of the given paths are writable: %r.' % paths)


def MakeApplication(stack_depth=2, **options):
  """Factory function to create an Application instance.

  For most purposes you will not need to use this function yourself, it will
  be called by Daemon(), Run() and Service() instead. However, you may wish to
  use it for your own Aplication purposes.

  Aside from the `stack_depth` argument, all named arguments are passed on to
  the initialization of the Application class. Refer to that class'
  documentation for a list of accepted arguments.

  Arguments
    % stack_depth: int ~~ 2
      From what level the stack frame should be taken. The default (2) uses the
      frame of the caller's caller, as it is used by the module's own functions.

  Returns:
    Application - application based on given frame and optional arguments.
  """
  # Need to grab the stack frame 2 up from here, as the first is the local
  # function here that gathers up data provided by this function.
  # pylint: disable=W0212
  caller_frame = sys._getframe(stack_depth)
  # pylint: enable=W0212
  return Application(caller_frame, **options)


def MakePaths(templates, replaces):
  """Returns paths from template strings and a fixed set of replacements."""
  return [template % replaces for template in templates]


def ReadConfig(config_file, local_path='.', read_paths=None, write_path=None):
  """Builds configuration from multiple configuration file locations.

  If `read_paths` is provided, the `config_file` is attempted to be read from
  each location in that iterable. If multiple paths contain a config file,
  statements are handled in proper UNIX fashion. That is, statements from the
  first occurrance are first read, and statements from following config files
  update or add to the existing config.

  if `read_paths` is not provided, or did not result in a configuration,
  the config file is read from the `local_path`, if provided.
  Then, if `write_path` is provided, the config is copied into the path
  specified by `write_path`, ensuring the config is read from a proper
  location at the next run.

  A RuntimeWarning is given under the following conditions:
    * `read_paths` provided, and exhaused without configuration.
    * `read_paths` not given or exhausted, and config does not exist locally.
    * `write_path` provided, but not writable when copying local config.

  Arguments:
    @ config_file: str
      Filename for the configuration file. This should be a relative path
    % local_path: str ~~ '.'
      Fallback location to find the config file on the local path. This will
      be used only in case `read_paths` is exhausted without result.
    % read_paths: iterable ~~ None
      Paths to search the `config_file` on. This is in addition
      to the default of searching the local module path
    % write_path: str ~~ None
      If provided, the local config file will be copied to this path.

  Raises:
    RuntimeError - If the `config_file` could not be found on any path.

  Returns:
    dict - Configuration dictionary as returned by ParseConfig.
  """

  if read_paths:
    config = {}
    for path in read_paths:
      config.update(ParseConfig(os.path.join(path, config_file)))
    if config:
      return config
    warnings.warn('Could not read config file %r from default paths:\n%s' %
                  (config_file, '\n'.join(read_paths)), RuntimeWarning)

  if local_path:
    config_local = os.path.join(local_path, config_file)
    if os.path.exists(config_local):
      config = ParseConfig(config_local)
      if write_path:
        try:
          if not os.path.isdir(write_path):
            os.makedirs(write_path)
          shutil.copy(config_local, write_path)
        except (IOError, OSError):
          warnings.warn(
              'Could not copy config file to %r' % write_path, RuntimeWarning)
      return config
    else:
      warnings.warn('Could not read config file %r from local path %r' %
                    (config_file, local_path), RuntimeWarning)
  raise RuntimeError('Configuration file could not be found anywhere.')


def ParseConfig(config_file):
  """Parses the given `config_file` and returns it as a nested dictionary."""
  parser = ConfigParser.SafeConfigParser()
  config_file = os.path.join(os.getcwd(), config_file)
  try:
    parser.read(config_file)
  except ConfigParser.ParsingError:
    raise ValueError('Not a valid config file: %r.' % config_file)
  return dict((section, dict(parser.items(section)))
              for section in parser.sections())


def SetUpLogging(log_filename, capacity=25, flush_level=logging.WARNING):
  """Sets up logging to log to be done in batches to an SQLite database.

  Arguments:
    @ log_filename
      The filename of the SQLite database to create or append the log to.
    % capacity: int ~~ 30
      The amount of logmessages that may be held in memory, delaying flushing.
      A smaller capacity means that logmessages are more often written to the
      database, and that less will be lost when the application exits uncleanly.
      The downside is more time spend in SQLite transactions and more disk IO.
    % flush_level: logging loglevel ~~ logging.WARNING
      The loglevel at which a flush will be forced, no matter the buffer level.
  """
  try:
    connection = extras.OpenSqliteLoggingDatabase(log_filename)
  except extras.sqlite.OperationalError:
    warnings.warn(WARNING_SQLITE_NODATABASE % log_filename, RuntimeWarning)
    logging.ROOT_LOGGER.AddHandler(logging.StreamHandler())
  else:
    logging.ROOT_LOGGER.AddHandler(handlers.BufferingDatabaseHandler(
        connection, capacity=capacity, flush_level=flush_level))
  logging.ROOT_LOGGER.SetLevel(logging.DEBUG)
  logging.LOG_MULTIPROCESSING = False  # Not available in python2.5.
  logging.RAISE_EXCEPTIONS = False  # Don't terminate app on logging error.


# ##############################################################################
# Modes to start a program in.
#
def Daemon(**options):
  """Runs the calling module's main() as a proper UNIX daemon.

  This sets up redirection of stdout and stderr, and the logging module.

  For argument information, refer to the documentation of the Application class.

  N.B. The caller is required to be in the global scope of the calling module.
  N.B. The function that will be ran inside the daemon is that module's main().
  """
  runner.DaemonRunner(MakeApplication(daemon=True, **options)).Start()


def Run(**options):
  """Runs the calling module's main() after setting up logging.

  For argument information, refer to the documentation of the Application class.
  """
  MakeApplication(**options).Run()


def Service(**options):
  """Runs the calling module's main() as a proper UNIX service.

  This sets up redirection of stdout and stderr, and the logging module.

  Use 'start', 'stop', and 'restart' to control the service.
  For argument information, refer to the documentation of the Application class.

  N.B. The caller is required to be in the global scope of the calling module.
  N.B. The function that will be ran inside the daemon is that module's main().
  """
  runner.DaemonRunner(MakeApplication(daemon=True, **options)).Execute()
