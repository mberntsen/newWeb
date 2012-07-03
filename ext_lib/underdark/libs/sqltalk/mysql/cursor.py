#!/usr/bin/python2.5
"""SQLTalk MySQL Cursor class.
"""
__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.12'

# Standard modules
import warnings
import weakref
import _mysql

# Custom modules
from underdark.libs.app import logging
from underdark.libs.sqltalk import sqlresult


class Cursor(object):
  """A base for Cursor classes. Useful attributes:

  description
    A tuple of DB API 7-tuples describing the columns in
    the last executed query; see PEP-249 for details.

  description_flags
    Tuple of column flags for last query, one entry per column
    in the result set. Values correspond to those in
    MySQLdb.constants.FLAG. See MySQL documentation (C API)
    for more information. Non-standard extension.

  Members:
    @ _connection: mysql.connection
      MySQLdb connection instance.
    @ errors: list
      MySQL errors for the most recently executed query

  Methods:
    Delete:           Remove row(s) from table.
    Describe:         Describe table in database or field in table.
    Drop:             Drops table(s) in database if it exists.
    Execute:          Executes a query without any processing
    Info:             Retrieve MySQL Server info.
    Insert:           Insert new row into table. Can perform multi-row insert.
    Select:           Select fields from table.
    Update:           Update values in table that match conditions.
    _ProcessWarnings: Processes warnings and messages from the MySQL server.
  """
  QUERY_DEBUG = '`%s` performed the following query:\n%s'

  def __init__(self, connection):
    self._connection = weakref.ref(connection)
    self.queries = []

  def _Execute(self, query):
    """Actually executes the query and returns the result of it.

    Arguments:
      @ query: basestring,
        Fully formatted sql statement to execute. In case of unicode, the
        string is encoded to the local character set before it is passed on
        to the server.

    Returns:
      sqlresult.ResultSet instance holding all query result data.
    """
    #TODO(Elmer): Fix this so that arguments can be given independent of the
    # query they belong to. This enables proper SelectTables and enables a host
    # of other escaping things to start working properly.
    #   Refer to MySQLdb.cursor code (~line 151) to see how this works.
    connection = self.connection
    if isinstance(query, unicode):
      log_query = query
    else:
      log_query = unicode(query, connection.charset, errors='replace')
    caller = logging.ScopeName(2)
    connection.logger.LogDebug(self.QUERY_DEBUG, caller, log_query)
    self.queries.append((caller, log_query))
    try:
      field_descriptions, result = connection.Query(query.strip())
      resultset = sqlresult.ResultSet(
          affected=connection.affected_rows(),
          charset=connection.charset,
          fields=field_descriptions,
          insertid=connection.insert_id(),
          query=query,
          result=result)
    except Exception:
      queries = '\n\n'.join(self.QUERY_DEBUG % query for query in self.queries)
      connection.logger.LogException(
          'Queries in this transaction (last one triggered):\n\n%s', queries)
      raise
    if connection.warning_count():
      self._ProcessWarnings(resultset)
    return resultset

  @staticmethod
  def _StringConditions(conditions, _unused_field_escape):
    if not conditions:
      return '1'
    elif not isinstance(conditions, basestring):
      return ' AND '.join(conditions)
    return conditions

  @staticmethod
  def _StringFields(fields, field_escape):
    if fields is None:
      return '*'
    elif isinstance(fields, basestring):
      return field_escape(fields)
    else:
      return ', '.join(field_escape(fields))

  @staticmethod
  def _StringGroup(group, field_escape):
    if group is None:
      return ''
    elif isinstance(group, basestring):
      return 'GROUP BY ' + field_escape(group)
    return 'GROUP BY ' + ', '.join(field_escape(group))

  @staticmethod
  def _StringLimit(limit, offset):
    if limit is None:
      return ''
    elif offset:
      return 'LIMIT %d OFFSET %d' % (limit, offset)
    return 'LIMIT %d' % limit

  @staticmethod
  def _StringOrder(order, field_escape):
    if order is None:
      return ''
    orders = []
    for rule in order:
      if isinstance(rule, basestring):
        orders.append(field_escape(rule))
      else:
        orders.append('%s %s' % (field_escape(rule[0]), ('', 'DESC')[rule[1]]))
    return 'ORDER BY ' + ', '.join(orders)

  @staticmethod
  def _StringTable(table, field_escape):
    if isinstance(table, basestring):
      return field_escape(table)
    else:
      return ', '.join(field_escape(table))

  def Delete(self, table, conditions, order=None,
             limit=None, offset=0, escape=True):
    """Remove row(s) from table that match conditions, up to limit.

    Arguments:
      table:      string. Name of the table to delete.
      conditions: string/list/tuple (optional).
                  Where statements. Literal as string. AND'd if list/tuple.
                  THESE WILL NOT BE ESCAPED FOR YOU, EVER.
      order:      (nested) list/tuple (optional).
                  Defines sorting of table before updating, elements can be:
                    string: a field to order by (in default database order).
                    list/tuple of two elements:
                      1) string, field name to order by
                      2) bool, revserse; set this to True to reverse the order
      limit:      integer. Defines max number of rows to delete. Default: None.
      offset:     integer (optional). Number of rows to skip, requires limit.
      escape:     boolean. Defines whether table and field names should be
                  escaped. Set this to False if you want to make use of MySQL
                  functions on this query. Default True.

    Returns:
      sqlresult.ResultSet object.
    """
    field_escape = self.connection.EscapeField if escape else lambda x: x
    return self._Execute('delete from %s where %s %s %s' % (
        self._StringTable(table, field_escape),
        self._StringConditions(conditions, field_escape),
        self._StringOrder(order, field_escape),
        self._StringLimit(limit, offset)))

  def Describe(self, table, field=''):
    """Describe table in database or field in table.

    Takes
      table: string. Name of the table to describe.
      field: string (optional). Field name to describe.

    Returns:
      sqlresult.ResultSet object.
    """
    return self._Execute('DESC %s %s' % (
        self._StringTable(table, self.connection.EscapeField),
        self._StringFields(field, self.connection.EscapeField)))

  def Execute(self, query):
    """Executes a raw query."""
    return self._Execute(query)

  def Insert(self, table, values, escape=True):
    """Insert new row into table.

    This method can also perform multi-row insert.
    By default, input strings are quoted, made safe to be inserted into MySQL
    and the Python None-object is translated to MySQL 'NULL'.

    Arguments:
      table:   string. Name of the table to insert into.
      values:  dictionary or list/tuple.
               Dictionary for single inserts:
               * keys:   field names
               * values: field values
               List of dictionaries for a multi-row insert:
               * Each record as a single dictionary.
               * Each dictionary should have the same keys (fields).
      escape:  boolean. Defines whether table names, fields and values should
               be escaped. Set this to False if you want to make use of
               MySQL functions on this query. Default True.

    Returns:
      sqlresult.ResultSet object.
    """
    if not values:
      raise ValueError('Must insert 1 or more value')
    values = self.connection.EscapeValues(values) if escape else values
    table = self.connection.EscapeField(table) if escape else table
    try:
      # Single insert
      values = ', '.join('`%s`=%s' % value for value in values.iteritems())
      query = 'INSERT INTO %s SET %s' % (table, values)
    except AttributeError:
      # Multi-row insert
      fields = ', '.join(map(self.connection.EscapeField, values[0]))
      values = ', '.join('(%s)' % ', '.join(row.itervalues()) for row in values)
      query = 'INSERT INTO %s (%s) VALUES %s' % (table, fields, values)
    return self._Execute(query)

  def Select(self, table, fields=None, conditions=None, order=None,
             group=None, limit=None, offset=0, escape=True, totalcount=False):
    """Select fields from table that match the conditions, ordered and limited.

    Arguments:
      table:      string/list/tuple. Table(s) to select fields out of.
      fields:     string/list/tuple (optional). Fields to select. Default '*'.
                  As string, single field name. (autoquoted)
                  As list/tuple, one field name per element. (autoquoted)
      conditions: string/list/tuple (optional). SQL 'where' statement.
                  Literal as string. AND'd if list/tuple.
                  THESE WILL NOT BE ESCAPED FOR YOU, EVER.
      order:      (nested) list/tuple (optional).
                  Defines sorting of table before updating, elements can be:
                    string: a field to order by (in default database order).
                    list/tuple of two elements:
                      1) string, field name to order by
                      2) bool, revserse; set this to True to reverse the order
      group:      str (optional). Field name or function to group result by.
      limit:      integer (optional). Defines output size in rows.
      offset:     integer (optional). Number of rows to skip, requires limit.
      escape:     boolean. Defines whether table and field names should be
                  escaped. Set this to False if you want to make use of MySQL
                  functions on this query. Default True.
      totalcount: boolean. If this is set to True, queries with a LIMIT applied
                  will have the full number of matching rows on
                  the affected_rows attribute of the resultset.

    Returns:
      sqlresult.ResultSet object.
    """
    field_escape = self.connection.EscapeField if escape else lambda x: x
    result = self._Execute('SELECT %s %s FROM %s WHERE %s %s %s %s' % (
        'SQL_CALC_FOUND_ROWS' if totalcount and limit is not None else '',
        self._StringFields(fields, field_escape),
        self._StringTable(table, field_escape),
        self._StringConditions(conditions, field_escape),
        self._StringGroup(group, field_escape),
        self._StringOrder(order, field_escape),
        self._StringLimit(limit, offset)))

    if totalcount and limit is not None and limit == len(result):
      result.affected = self._Execute('SELECT FOUND_ROWS()')[0][0]
    return result

  def SelectTables(self, contains=None, exact=False):
    """Returns table names from the current database.

    Arguments
      % contains: str ~~ ''
        A substring required to be present in all returned table names.
      % exact: bool ~~ False
        Flags whether the string given in contains should be the exact name.

    Returns:
      set: tables names that match the filter.
    """
    if contains:
      contains = self.connection.EscapeValues(contains)
      if exact:
        result = self._Execute('SHOW TABLES LIKE %s' % contains)
      else:
        # Strip quotes from escaped string to allow insertion of wildcards.
        result = self._Execute('SHOW TABLES LIKE "%%%s%%"' % (
            contains.strip("'")))
    else:
      result = self._Execute('SHOW TABLES')
    return set(result[result.fieldnames[0]])

  def Truncate(self, table):
    """Truncate table in database, reducing it to 0 rows.

    Arguments:
      table: string, name of the table to truncate.

    Returns:
      sqlresult.ResultSet object.
    """
    return self._Execute('TRUNCATE %s' % (
        self._StringTable(table, self.connection.EscapeField)))

  def Update(self, table, values, conditions, order=None,
             limit=1, offset=None, escape=True):
    """Updates table records to the new values where conditions are met.

    Arguments:
      table:      string. Name of table to update values in.
      values:     dictionary. Key for fieldname, value for content (autoquoted).
      conditions: string/list/tuple.
                  Where statements. Literal as string. AND'd if list/tuple.
                  THESE WILL NOT BE ESCAPED FOR YOU, EVER.
      order:      (nested) list/tuple (optional).
                  Defines sorting of table before updating, elements can be:
                    string: a field to order by (in default database order).
                    list/tuple of two elements:
                      1) string, field name to order by
                      2) bool, revserse; set this to True to reverse the order
      limit:      integer (optional). Defines update max size in rows.
                  Default 1, set to 0 for no limit.
      offset:     integer (optional). Number of rows to skip, requires limit.
      escape:     boolean. Defines whether table names, fields and values should
                  be escaped. Set this to False if you want to make use of
                  MySQL functions on this query. Default True.

    Returns:
      sqlresult.ResultSet object.
    """
    if escape:
      field_escape = self.connection.EscapeField
      values = self.connection.EscapeValues(values)
    else:
      field_escape = lambda x: x

    return self._Execute('UPDATE %s SET %s WHERE %s %s %s' % (
        self._StringTable(table, field_escape),
        ', '.join('`%s`=%s' % value for value in values.iteritems()),
        self._StringConditions(conditions, field_escape),
        self._StringOrder(order, field_escape),
        self._StringLimit(limit, offset)))

  def _ProcessWarnings(self, resultset):
    """Updates messages attribute with warnings given by the MySQL server."""
    db_info = self.connection.info()
    db_warnings = self.connection.ShowWarnings()
    if db_warnings:
      # This is done in two loops in case Warnings are set to raise exceptions.
      for warning in db_warnings:
        self.connection.logger.LogWarning('%d: %s' % warning[1:])
        resultset.warnings.append(warning)
      for warning in db_warnings:
        warnings.warn(warning[-1], self.Warning, 3)
    elif db_info:
      self.connection.logger.LogWarning('%d: %s' % db_info[1:])
      resultset.warnings.append(db_info)
      warnings.warn(db_info, self.Warning, 3)

  @property
  def connection(self):
    """Returns the connection that this cursor belongs to."""
    connection = self._connection()
    if connection is None:
      raise self.ProgrammingError('Connection for this cursor closed.')
    return connection


  DatabaseError = _mysql.DatabaseError
  DataError = _mysql.DataError
  Error = _mysql.Error
  IntegrityError = _mysql.IntegrityError
  InterfaceError = _mysql.InterfaceError
  InternalError = _mysql.InternalError
  NotSupportedError = _mysql.NotSupportedError
  OperationalError = _mysql.OperationalError
  ProgrammingError = _mysql.ProgrammingError
  Warning = _mysql.Warning
