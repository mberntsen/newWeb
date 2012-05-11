#!/usr/bin/python2.5
"""SQL result abstraction module.

Classes:
  ResultRow: Dict-like object that represents a single database result row.
  ResultSet: Abstraction for a database resultset.

Error Classes:
  Error: Exception base class.
  FieldError: Field- index or name does not exist.
  NotSupportedError: Operation is not supported
"""
__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '1.2'

# Standard modules
import operator


class Error(Exception):
  """Exception base class."""


class FieldError(Error, IndexError, KeyError):
  """Field- index or name does not exist."""


class NotSupportedError(Error, TypeError):
  """Operation is not supported."""


class ResultRow(dict):
  """SQL Result row - an ordered dictionary-like record abstraction.

  ResultRow has two item retrieval interfaces:
    1) Key-based access like that of a dictionary.
    2) Indexed access like a tuple. (field-order is preserved)

  Members:
    % names: tuple (read-only)
      Names for the fields that the ResultRow contains.
  """
  def __init__(self, *args, **kwds):
    """Sets up the ordered dict.

    Arguments:
      @ *args: dict / iterator
        A dictionary or pairwise iterable object to source the dictionary from.
      @ **kwds
        key=value pairs to populate the dictionary from.
    """
    if len(args) > 1:
      raise TypeError('expected at most 1 argument, got %d' % len(args))
    if not hasattr(self, '_keys'):
      self._keys = []
    super(ResultRow, self).__init__()
    self._dict = super(ResultRow, self)
    self.update(*args, **kwds)

  def __eq__(self, other):
    """Checks equality of the ResultRow to another ResultRow or object.

    A ResultRow can only be equal to another ResultRow, and then only if both
    fieldnames and fieldvalues are the same (data and order).
    """
    if self is other:
      return True
    elif isinstance(other, self.__class__):
      return self.items() == other.items()
    return False

  def __getitem__(self, key):
    try:
      if isinstance(key, int):
        return self.values()[key]
      else:
        return super(ResultRow, self).__getitem__(key)
    except (IndexError, KeyError), message:
      raise FieldError(message)

  def __repr__(self):
    """Returns a string representation of the ResultRow."""
    return '%s(%s)' % (self.__class__.__name__,
                       ', '.join('%s=%r' % item for item in self.iteritems()))

  def get(self, key, default=None):
    try:
      return self[key]
    except FieldError:
      return default

  @property
  def names(self):
    """Returns the fieldnames of the ResultRow as a tuple."""
    return self.keys()

  # ############################################################################
  # Iteration on dictionary / record entries
  #
  def __iter__(self):
    """Returns an iterator for the values of the ResultRow."""
    return self.itervalues()

  def __reversed__(self):
    """Returns a reversed key iterator."""
    return reversed(self._keys)

  def iterkeys(self):
    return iter(self._keys)

  def itervalues(self):
    return (self[key] for key in self._keys)

  def iteritems(self):
    return ((key, self[key]) for key in self._keys)

  def keys(self):
    return list(self.iterkeys())

  def values(self):
    return list(self.itervalues())

  def items(self):
    return list(self.iteritems())

  # ############################################################################
  # Methods to keep the dictionary neat and ordered
  #
  def __delitem__(self, key):
    """Removes a key and its value from the dictionary."""
    self._dict.__delitem__(key)
    self._keys.remove(key)

  def __setitem__(self, key, value):
    """Sets or updates a dictionary value."""
    if key not in self:
      self._keys.append(key)
    self._dict.__setitem__(key, value)

  def clear(self):
    """Clears the contents of the dictionary."""
    del self._keys[:]
    self._dict.clear()

  def pop(self, key, *default):
    try:
      self._keys.remove(key)
    except ValueError:
      return default[0]
    return self._dict.pop(key)

  def popitem(self):
    """Pops the key,value pair at the end of the dictionary."""
    if not self:
      raise KeyError
    key = self._keys.pop()
    return key, self._dict.pop(key)

  def setdefault(self, key, default=None):
    try:
      return self[key]
    except KeyError:
      self[key] = default
      return default

  def update(self, other=(), **kwds):
    try:
      # Tuple has no attribute iteritems; correct but not relevant
      # pylint: disable=E1103
      for key, value in other.iteritems():
        self[key] = value
      # pylint: enable=E1103
    except AttributeError:
      for key, value in other:
        self[key] = value
    for key, value in kwds.iteritems():
      self[key] = value


class ResultSet(object):
  """SQL Result set - stores the query, the returned result, and other info.

  !! This class defines __slots__.

  ResultSet is created from immutable objects. Once defined, none of its
  attributes can be altered or overwritten. The exception to this is the private
  member _fieldnames which has to be a list for fieldname lookup purposes.

  Members:
    @ affected - int
      Number of rows affected by last action.
    @ charset - str
      Character set used for this connection.
    @ fields - tuple
      Fields in the ResultSet. Each field is a tuple of 7 elements as specified
      by the Python DB API (v2).
    @ insertid - int
      Auto-increment ID that was generated upon the last insert.
    @ pivoted - bool
      states whether the result set has been pivoted.
    @ query - str
      The executed query that gave this result set.
    @ result:   tuple
      SQL Result set for the last executed query.
    @ _fieldnames - list
      Names of the fields in the result, used for reverse-indexing.
    % fieldnames - tuple (read-only)
      Names of the fields in the result.
  """
  __slots__ = ('affected', 'charset', 'fields', 'insertid',
               'pivoted', 'query', 'result', 'warnings', '_fieldnames')

  def __init__(self, query='', charset='', result=None, fields=None,
               affected=0, insertid=0, pivoted=False):
    """Initializes a new ResultSet.

    Arguments:
      % affected: int ~~ 0
        Number of affected rows from this operation.
      % charset: str ~~ ''
        Character set used by the connection that executed this operation.
      % fields: tuple of tuples of strings ~~ None
        Description of fields involved in this operation. Tuples of strings as
        per the Python DB API (v2).
      % insertid: int ~~ 0
        Auto-increment ID that was generated upon the last insert.
      % query ~~ ''
        The query that was executed for this operation.
      % result ~~ None
        SQL Result set for the this operation.
      % pivoted ~~ False
        Flags whether the result argument is pivoted or not.
    """
    self.affected = affected
    self.charset = charset
    self.insertid = insertid
    self.pivoted = pivoted
    self.query = query
    self.warnings = []

    if result:
      self.fields = tuple(fields)
      get_name = operator.itemgetter(0)
      self._fieldnames = map(get_name, fields)
      if pivoted:
        self.result = ResultRow(zip(self._fieldnames, result))
      else:
        self.result = tuple(ResultRow(zip(self._fieldnames, row))
                            for row in result)
    else:
      self.fields = ()
      self._fieldnames = []
      self.result = ()

  def __eq__(self, other):
    """Checks equality of the ResultSet to another ResultSet or object.

    A ResultSet can only be equal to another ResultSet, and then only if all
    their public members (except pivot state) compare equal.
    """
    if self is other:
      return True
    elif isinstance(other, self.__class__):
      return (self.affected == other.affected and
              self.insertid == other.insertid and
              self.fields == other.fields and
              self.result == other.result)
    else:
      return False

  def __getitem__(self, item):
    """Returns a row or column from the ResultSet by either index or fieldname.

    Arguments:
      @ item: int / str
        Rownumber or fieldname:
        - If given a rownumber, the corresponding ResultRow is returned.
        - If given a fieldname, a tuple with the field's values is returned.
        If performed on a pivoted ResultSet, the result if not yet defined.

    Returns:
      ResultRow / tuple: As detailed in the Arguments section.
    """
    try:
      return self.result[item]
    except FieldError:
      raise
    except IndexError:
      raise FieldError('Bad field index: %r.' % item)
    except TypeError:
      # The item type is incorrect, try grabbing a column for this fieldname.
      try:
        index = self._fieldnames.index(item)
        return tuple(row[index] for row in self.result)
      except ValueError:
        raise FieldError('Bad field name: %r.' %  item)

  def __iter__(self):
    """Returns an iterator for the contained ResultRows."""
    return iter(self.result)

  def __len__(self):
    """Returns an integer equal to the number of rows contained."""
    return len(self.result)

  def __nonzero__(self):
    """Boolean truthness of the ResultSet. True if it has 1+ ResultRow"""
    return any(self.result)

  def __repr__(self):
    """Returns a string representation of the ResultSet."""
    info = (('Result: %d row%s', 'Pivoted result: %d field%s')[self.pivoted] %
            (len(self.result), 's'[len(self.result) == 1:]))
    return '%s instance at %s. %s' % (
        self.__class__.__name__, hex(id(self)).rstrip('L'), info)

  def FilterRowsByFields(self, *fields):
    """Yields ResultRows containing only selected fields.

    N.B. This method does not work for Pivoted ResultSet objects.

    Arguments:
      @ *fields: list of str
        The fieldnames to filter.

    Raises:
      BadFieldError: One of the given fieldnames did not exist.
      NotSupportedError: A pivoted ResultSet does not support this method.

    Yields:
      ResultRow: Each ResultRow contains only the filtered fields.
    """
    if self.pivoted:
      raise NotSupportedError('Operation is not supported on pivoted ResultSet')
    try:
      indices = tuple(self._fieldnames.index(field) for field in fields)
    except ValueError:
      raise FieldError('Bad fieldnames in filter request.')
    for row in self:
      yield ResultRow(zip(fields, tuple(row[index] for index in indices)))

  def Pivot(self):
    """Returns a new QueryResult object with a pivoted data-set.

    All the other portions of the object are left as-is. This means that
    pivoting a QueryResult object twice yields the same object you started with.

    Returns:
      ResultSet: same as original but with pivoted result set.
    """
    return self.__class__(affected=self.affected,
                          charset=self.charset,
                          fields=self.fields,
                          insertid=self.insertid,
                          pivoted=not self.pivoted,
                          query=self.query,
                          result=zip(*self.result),
                          warnings=self.warnings)

  @property
  def fieldnames(self):
    """Returns a tuple of the fieldnames that are in this ResultSet."""
    return tuple(self._fieldnames)
