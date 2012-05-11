#!/usr/bin/python2.5
"""This module implements the Connection class, which sets up a connection to
a MySQL database. From this connection, cursor objects can be created, which
use the escaping and character encoding facilities offered by the connection.
"""
__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.15'

# Standard modules
import _mysql
import threading
import weakref

# Custom modules
from underdark.libs.app import logging

# Application specific modules
import constants
import converters
import cursor


class Connection(_mysql.connection):
  """MySQL Database Connection Object"""
  def __init__(self, user, passwd, *args, **kwargs):
    """Create a connection to the database. It is strongly recommended
    that you only use keyword parameters. Consult the MySQL C API
    documentation for more information.

    Arguments:
      user:               string, user to connect as.
      passwd:             string, password to use.
      db:                 string, database to use. Default same as user.
      host:               string, host to connect to. Default 'localhost'.
      port:               integer, TCP/IP port to connect to.
      unix_socket:        string, location of unix_socket to use.
      conv:               conversion dictionary, see converters module.
      connect_timeout:    number of seconds to wait before the connection
                          attempt fails.
      compress:           bool, enable compression. Default False
      named_pipe:         if set, a named pipe is used to connect (Windows only)
      init_command:       command which is run once the connection is created
      read_default_file:  file from which default client values are read
      read_default_group: configuration group to use from the default file
      use_unicode:        If True, text-like columns are returned as unicode
                          objects using the connection's character set.
                          Otherwise, text-like columns are returned as strings.
                          Columns are returned as normal strings. Unicode
                          objects will always be encoded to the connection's
                          character set regardless of this setting.
      charset:            If supplied, the connection character set will be
                          changed to this character set (MySQL-4.1 and newer).
                          This enforces use_unicode=True.
      sql_mode:           If supplied, the session SQL mode will be changed to
                          this setting (MySQL-4.1 and newer). For more details
                          and legal values, see the MySQL documentation.
      client_flag:        integer, flags to use or 0.
                          (see MySQL docs or constants/CLIENTS.py)
      ssl:                dictionary or mapping, contains SSL connection
                          parameters; see the MySQL documentation for more
                          details (mysql_ssl_set()).  If this is set, and the
                          client does not support SSL, NotSupportedError will
                          be raised.
      local_infile:       bool, True enables LOAD LOCAL INFILE, False disables.
                          Default False

    There are a number of undocumented, non-standard arguments. See the
    documentation for the MySQL C API for some hints on what they do.
    """
    kwargs['user'] = user
    kwargs['passwd'] = passwd
    kwargs['host'] = kwargs.get('host', 'localhost')
    kwargs['db'] = kwargs.get('db', user)

    self.logger = logging.GetLogger('mysql_%s' % kwargs['db'])
    if kwargs.pop('debug', False):
      self.logger.SetLevel(logging.DEBUG)
    else:
      self.logger.SetLevel(logging.WARNING)
    if kwargs.pop('disable_log', False):
      self.logger.disable_logger = True

    self.encoders = {}
    converts = {}
    for key, value in converters.CONVERSIONS.iteritems():
      if not isinstance(key, int):
        self.encoders[key] = value
      else:
        if isinstance(value, list):
          converts[key] = value[:]
        else:
          converts[key] = value
    kwargs.setdefault('conv', {}).update(converts)

    autocommit = kwargs.pop('autocommit', None)
    charset = kwargs.pop('charset', 'utf8')
    sql_mode = kwargs.pop('sql_mode', None)
    use_unicode = kwargs.pop('use_unicode', False) or bool(charset)

    client_version = tuple(int(n) for n in
                           _mysql.get_client_info().split('.')[:2])
    kwargs.setdefault('client_flag', 0)
    if client_version >= (4, 1):
      kwargs['client_flag'] |= constants.CLIENT.MULTI_STATEMENTS
    if client_version >= (5, 0):
      kwargs['client_flag'] |= constants.CLIENT.MULTI_RESULTS

    # Done redefining variables for initialization. Engage _mysql!
    super(Connection, self).__init__(*args, **kwargs)

    self.server_version = tuple(
        map(int, self.get_server_info().split('.')[:2]))

    if sql_mode:
      self.SetSqlMode(sql_mode)

    # The following voodoo is necssary to avoid double references that would
    # prevent a connection object from being finalized and collected properly.
    db = weakref.proxy(self)
    def _GetStringLiteral():
      def StringLiteral(string, _dummy=None):
        """Returns the SQL literal (safe) for the given string."""
        return db.string_literal(string)
      return StringLiteral

    def _GetUnicodeLiteral():
      def UnicodeLiteral(u_string, _dummy=None):
        """Returns the SQL (safe) literal for the given unicode object."""
        return db.EscapeValues(u_string.encode(db.charset))
      return UnicodeLiteral

    def _GetStringDecoder():
      def StringDecoder(string):
        """Returns the unicode codepoints for an encoded bytestream."""
        return string.decode(db.charset)
      return StringDecoder

    self.string_decoder = _GetStringDecoder()
    self.encoders[str] = _GetStringLiteral()
    self.encoders[unicode] = self.unicode_literal = _GetUnicodeLiteral()

    if use_unicode:
      decoder = (None, self.string_decoder)
      self.converter[constants.FIELD_TYPE.STRING].append(decoder)
      self.converter[constants.FIELD_TYPE.VAR_STRING].append(decoder)
      self.converter[constants.FIELD_TYPE.VARCHAR].append(decoder)
      self.converter[constants.FIELD_TYPE.BLOB].append(decoder)
    self._charset = None
    self.charset = charset or self.character_set_name()

    self.transactional = bool(self.server_capabilities &
                              constants.CLIENT.TRANSACTIONS)
    self._autocommit = None
    if autocommit is not None:
      self.autocommit = autocommit
    else:
      self.autocommit = not self.transactional
    self.lock = threading.Lock()
    self.messages = []

  def __enter__(self):
    """Refreshes the connection and returns a cursor, starting a transaction."""
    if self.lock.acquire(False):  # Don't block. fail when it's in use.
      self.ping(True)
      self.ping(self.autocommit)
      self.TransactionTimer()
      return cursor.Cursor(self)
    raise self.OperationalError(
        'A transaction is already open for this connection.')

  def __exit__(self, exc_type, exc_value, _exc_traceback):
    """End of transaction: commits on success, or rolls back on failure."""
    if exc_type:
      self.rollback()
      self.logger.LogWarning(
          'The transaction was rolled back after the following exception '
          'occurred:\n  %s\nConnected to server: %r',
          logging.ExceptionLine(exc_type, exc_value), self.get_host_info())
    else:
      self.commit()
      self.logger.LogDebug(
          'Transaction committed (server: %r).', self.get_host_info())
    self.transaction_timer.cancel()
    self.lock.release()

  def CurrentDatabase(self):
    """Return the name of the currently used database"""
    _description, result = self.Query('SELECT DATABASE()')
    if result:
      return result[0][0]

  def EscapeField(self, field):
    """Returns a SQL escaped field or table name."""
    if not field:
      return ''
    elif isinstance(field, basestring):
      fields = '.'.join('`%s`' % f.replace('`', '``') for f in field.split('.'))
      return fields.replace('`*`', '*')
    else:
      return map(self.EscapeField, field)

  def EscapeValues(self, obj):
    """Escapes any object passed in following the encoders dictionary.

    Sequences and mappings will only have their contents escaped. All strings
    will be encoded to the connection's character set.
    """
    return self.escape(obj, self.encoders)

  def Info(self):
    """Returns a dictionary of MySQL server info and current active database.

    Returns
      dictionary: keys: 'db', 'charset', 'server'
    """
    #TODO(Elmer): Make this return more useful information and statistics
    return {'db': self.CurrentDatabase(),
            'charset': self.charset,
            'server': self.ServerInfo()}

  def Query(self, query_string):
    if isinstance(query_string, unicode):
      # This might not actually be necessary given that EscapeValues does this.
      query_string = query_string.encode(self.charset)

    self.query(query_string)
    stored_result = self.store_result()
    if stored_result:
      return stored_result.describe(), stored_result.fetch_row(0)
    return None, None

  def ServerInfo(self):
    """Returns a mysql specific set of server information"""
    return self.get_server_info()

  def SetSqlMode(self, sql_mode):
    """Set the connection sql_mode. See MySQL documentation for legal values."""
    if self.server_version < (4, 1):
      raise self.NotSupportedError('server is too old to set sql_mode')
    self.query('SET SESSION sql_mode="%s"' % sql_mode)
    self.store_result()

  def ShowWarnings(self):
    """Return detailed information about warnings as a sequence of tuples of
    (Level, Code, Message). This is only supported in MySQL-4.1 and up.
    If your server is an earlier version, an empty sequence is returned."""
    if self.server_version < (4, 1):
      return ()
    self.query('SHOW WARNINGS')
    return self.store_result().fetch_row(0)

  def TransactionTimer(self, delay=60):
    caller = logging.ScopeName(2)
    def Warn():
      self.logger.LogWarning(
          'Transaction started by %s is open for more than %s seconds.',
          caller, delay)
    self.transaction_timer = threading.Timer(delay, Warn)
    self.transaction_timer.daemon = True
    self.transaction_timer.start()

  def _GetAutocommitState(self):
    """This returns the current setting for autocommiting transactions."""
    return self._autocommit

  def _GetCharacterSet(self):
    """This configures the character set used by this connection.

    Character sets should be specified as known and supported by MySQL.
    """
    return self._charset

  def _SetAutocommitState(self, state):
    """This sets the autocommit mode on the connection.

    This is False by default if the database supports transactions."""
    self.ping(state)
    super(Connection, self).autocommit(state)
    self._autocommit = state

  def _SetCharacterSet(self, charset):
    """This sets the character set, refer to _GetCharacterSet for doc."""
    if charset != self._charset:
      super(Connection, self).set_character_set(charset)
      self._charset = charset

  autocommit = property(_GetAutocommitState, _SetAutocommitState)
  charset = property(_GetCharacterSet, _SetCharacterSet)

  # Error classes taken from _mysql
  Error = _mysql.Error
  InterfaceError = _mysql.InterfaceError
  DatabaseError = _mysql.DatabaseError
  DataError = _mysql.DataError
  OperationalError = _mysql.OperationalError
  IntegrityError = _mysql.IntegrityError
  InternalError = _mysql.InternalError
  ProgrammingError = _mysql.ProgrammingError
  NotSupportedError = _mysql.NotSupportedError
  Warning = _mysql.Warning
