#!/usr/bin/python
"""uWeb model base classes."""
from __future__ import with_statement

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.9'

# Standard modules
import sys

class Error(Exception):
  """Superclass used for inheritance and external exception handling."""


class AlreadyExistError(Error):
  """The resource already exists, and cannot be created twice."""


class NotExistError(Error):
  """The requested or provided resource doesn't exist or isn't accessible."""


class PermissionError(Error):
  """The entity has insufficient rights to access the resource."""


class Record(dict):
  """Basic class for database table/record abstraction."""
  _PRIMARY_KEY = 'ID'
  _FOREIGN_RELATIONS = {}
  _TABLE = None

  def __init__(self, connection, record):
    """Initializes a Record instance.

    Arguments:
      @ connection: sqltalk.connection
        The database connection to use for further queries.
      @ record: dict / sqltalk.ResultSet
        A field-based mapping of the database record information.
    """
    super(Record, self).__init__(record)
    self.connection = connection
    if not hasattr(Record, '._SUBTYPES'):
      # Adding classes at runtime is pretty rare, but fails this code.
      # Pylint believes Record has no method __subclasses__
      # pylint: disable=E1101
      Record._SUBTYPES = dict(
          (cls.TableName(), cls) for cls in Record.__subclasses__())
      # pylint: enable=E1101

  def __hash__(self):
    """Returns the hashed value of the key."""
    return hash(self.key)

  def __int__(self):
    """Returns the integer key value of the Record.

    For record objects where the primary key value is not (always) an integer,
    this function will raise an error in the situations where it is not.
    """
    if not isinstance(self.key, (int, long)):
      # We should not truncate floating point numbers.
      # Nor turn strings of numbers into an integer.
      raise ValueError('The primary key is not an integral number.')
    return self.key

  # ############################################################################
  # Methods enabling rich comparison
  #
  def __eq__(self, other):
    """Simple equality comparison for database objects.

    To compare equal, two objects must:
      1) Be of the same type;
      2) Have the same primary key
      3) Have the same content.

    In the case that the compared objects have foreign relations, these  will be
    compared as well (recursively). If only one of the objects has foreign
    relations loaded, only the primary key value will be compared to the value
    in the other Record.
    """
    print 'start comparison'
    if type(self) != type(other):
      return False
    if self.key is None or self.key != other.key:
      return False
    for local, remote in zip(self.values(), other.values()):
      if (isinstance(local, Record) + isinstance(remote, Record)) % 2:
        if (isinstance(local, Record) and local.key != remote or
            isinstance(remote, Record) and remote.key != local):
          return False
      elif local != remote:
        return False
    return True

  def __ne__(self, other):
    """Returns the proper inverse of __eq__.

    Without this, the non-equal checks used in __eq__ will not work, and the
    `!=` operator will not be the logical inverse of `==`.
    """
    return not self == other

  # ############################################################################
  # Methods enabling auto-loading
  #
  def __getitem__(self, field):
    """Returns the value corresponding to a given `field`.

    If a field represents a foreign relation, this will be delegated to
    the `_LoadForeign` method.
    """
    value = super(Record, self).__getitem__(field)
    return self._LoadForeign(field, value)

  def _LoadForeign(self, field, value):
    """Loads and returns objects referenced by foreign key.

    This is done by checking the `field` against the class' `_FOREIGN_RELATIONS`
    mapping. If a match is found, `_LoadForeignFromRelationsTable` is executed
    and its return value returned.

    If the `field` is not present in the class mapping, it will be checked
    against table names for each of the subclasses of Record. This mapping is
    maintained in `_SUBTYPES`. If a match is found, an instance of the
    corresponding class will replace the existing value, and will subsequently
    be returned.

    If the `field` is not present in either mapping, its value will remain
    unchanged, and returned as such.

    N.B. If the field name the same as the record's `TableName`, it will NOT be
    automatically resolved. The assumption is that the field will not contain a
    meaningful reference. This behavior can be altered by specifying the
    relation in the _FOREIGN_RELATIONS class constant.

    Arguments:
      @ field: str
        The field name to be checked for foreign references
      @ value: obj
        The current value for the field. This is used as primary key in case
        of foreign references.

    Returns:
      obj: The value belonging to the given `field`. In case of resolved foreign
           references, this will be the referenced object. Else it's unchanged.
    """
    if not isinstance(value, Record):
      if field in self._FOREIGN_RELATIONS:
        return self._LoadUsingForeignRelations(
            self._FOREIGN_RELATIONS[field], field, value)
      elif field == self.TableName():
        return value
      elif field in self._SUBTYPES:
        value = self._SUBTYPES[field].FromKey(self.connection, value)
        self[field] = value
    return value

  def _LoadUsingForeignRelations(self, cls, field, value):
    """Loads and returns foreign relation based on given class (name).

    The action taken depends on the given `cls`. If the given class is None (or
    otherwise boolean false), no action will be taken, and the value will be
    returned unchanged.

    If the class is given as string, it will be loaded from the current module.
    It should be a proper subclass of Record, after which the current `value` is
    used to create a record using `cls.FromKey`.

    Arguments:
      @ cls: None / type / str
        The class name or actual type to create an instance from.
      @ field: str
        The field name to be checked for foreign references
      @ value: obj
        The current value for the field. This is used as primary key in case
        of foreign references.

    Raises:
      ValueError: If the class name cannot be found, or the type is not a
                  subclass of Record.

    Returns:
      obj: The value belonging to the given `field`. In case of resolved foreign
           references, this will be the referenced object. Else it's unchanged.
    """
    if not cls:
      return value
    if isinstance(cls, basestring):
      try:
        cls = getattr(sys.modules[self.__module__], cls)
      except AttributeError:
        raise ValueError(
            'Bad _FOREIGN_RELATIONS map: Target %r not a class in %r' % (
                cls, self.__module__))
    if not issubclass(cls, Record):
      raise ValueError('Bad _FOREIGN_RELATIONS map: '
                       'Target %r not a subclass of Record' % cls.__name__)
    value = cls.FromKey(self.connection, value)
    self[field] = value
    return value

  # ############################################################################
  # Methods for proper representation of the Record object
  #
  def __repr__(self):
    return '%s(%s)' % (self.__class__.__name__, super(Record, self).__repr__())

  def __str__(self):
    return '%s({%s})' % (
        self.__class__.__name__,
        ', '.join('%r: %r' % item for item in self.iteritems()))

  # ############################################################################
  # Methods needed to create functional dictionary likeness for value lookups
  #
  def get(self, key, default=None):
    """Returns the value for `key` if its present, otherwise `default`."""
    try:
      return self[key]
    except KeyError:
      return default

  def iteritems(self):
    """Yields all field+value pairs in the Record.

    N.B. This automatically resolves foreign references.
    """
    return ((key, self[key]) for key in self)

  def itervalues(self):
    """Yields all values in the Record, loading foreign references."""
    return (self[key] for key in self)

  def items(self):
    """Returns a list of field+value pairs in the Record.

    N.B. This automatically resolves foreign references.
    """
    return list(self.iteritems())

  def values(self):
    """Returns a list of values in the Record, loading foreign references."""
    return list(self.itervalues())

  # ############################################################################
  # Private methods to be used for development
  #
  def _GetChildren(self, child_class, relation_field=None):
    """Returns all `child_class` objects related to this record.

    The table for the given `child_class` will be queried for all fields where
    the `relation_field` is the same as this record's primary key (`self.key`).

    These records will then be yielded as instances of the child class.

    Arguments:
      @ child_class: Record
        The child class whose objects should be found.
      % relation_field: str ~~ self.TableName()
        The fieldname in the `child_class` table which related that table to
        the table for this record.
    """
    relation_field = relation_field or self.TableName()
    with self.connection as cursor:
      safe_key = self.connection.EscapeValues(self.key)
      children = cursor.Select(
          table=child_class.TableName(),
          conditions='`%s`=%s' % (relation_field, safe_key))
    for child in children:
      yield child_class(self.connection, child)

  def _RecordInsert(self, sql_record):
    """Inserts the given `sql_record` into the database.

    The table used to store this record is gathered from the `self.TableName()`
    property.
    Upon success, the record's primary key is set to the result's insertid
    """
    with self.connection as cursor:
      record = cursor.Insert(table=self.TableName(), values=sql_record)
    self.key = record.insertid

  def _RecordUpdate(self, sql_record):
    """Updates the existing database entry with values from `sql_record`.

    The table used to store this record is gathered from the `self.TableName()`
    property. The condition with which the record is updated is the name and
    value of the Record's primary key (`self._PRIMARY_KEY` and `self.key` resp.)
    """
    with self.connection as cursor:
      safe_key = self.connection.EscapeValues(self.key)
      update = cursor.Update(table=self.TableName(), values=sql_record,
                    conditions='`%s` = %s' % (self._PRIMARY_KEY, safe_key))
      if not update.affected:
        cursor.Insert(table=self.TableName(), values=sql_record)

  @classmethod
  def DeleteKey(cls, connection, pkey_value):
    """Deletes a database record based on the primary key value.

    Arguments:
      @ connection: sqltalk.connection
        Database connection to use.
      @ pkey_value: obj
        The value for the primary key field
    """
    with connection as cursor:
      safe_key = connection.EscapeValues(pkey_value)
      cursor.Delete(table=cls.TableName(),
                    conditions='`%s` = %s' % (cls._PRIMARY_KEY, safe_key))

  @classmethod
  def FromKey(cls, connection, pkey_value):
    """Returns the Record object that belongs to the given primary key value.

    Arguments:
      @ connection: sqltalk.connection
        Database connection to use.
      @ pkey_value: obj
        The value for the primary key field

    Raises:
      NotExistError:
        There is no Record for that primary key value.

    Returns:
      Record: Database record abstraction class.
    """
    with connection as cursor:
      safe_key = connection.EscapeValues(pkey_value)
      record = cursor.Select(
          table=cls.TableName(),
          conditions='`%s` = %s' % (cls._PRIMARY_KEY, safe_key))
    if not record:
      raise NotExistError('There is No %r with key %r' % (
          cls.__name__, pkey_value))
    return cls(connection, record[0])

  def Delete(self):
    """Deletes a loaded record based on `self.TableName` and `self.key`.

    For deleting an unloaded object, use the classmethod `DeleteKey`.
    """
    with self.connection as cursor:
      cursor.Delete(table=self.TableName(), conditions='`%s` = %s' % (
          self._PRIMARY_KEY, self.connection.EscapeValues(self.key)))

  @classmethod
  def List(cls, connection):
    """Yields a Record object for every table entry.

    Arguments:
      @ connection: sqltalk.connection
        Database connection to use.

    Yields:
      Repository: repository abstraction class.
    """
    with connection as cursor:
      repositories = cursor.Select(table=cls.TableName())
    for repository in repositories:
      yield cls(connection, repository)

  #XXX(Elmer): We might want to use a single transaction to Save() (or not save)
  # all this object's children. Doing so would require a second optional
  # argument, cursor, and some delegation to a separate save method which
  # REQUIRES a cursor. (to reduce the copy/paste redundancy of two branches)
  def Save(self, save_foreign=False):
    """Saves or updated the record, based on `self.TableName()` and `self.key`.

    Firstly, it makes a strictly data containing SQL record. This means that any
    record class contained by the record is reduced to that record's primary key
    (by use of the `key` property). If flagged to do so, it is at this point
    that the foreign record will be recursively `Save()`d.

    Once the clean `sql_record` is obtained, a check is performed to see whether
    the object should be inserted into the database, or updated there.
    This is done by checking the value of the record's own primary key.

    If this key is set (is not None), the `sql_record` will be handed off to
    the `_RecordUpdate()` method, which will update the existing database entry.
    In the other case, the `sql_record` will be handed off to the
    `_RecordInsert()` method which will create the database entry.

    Arguments:
      % save_foreign: bool ~~ False
        If set, each Record (subclass) contained by this one will be saved as
        well. This recursive saving triggers *before* this record itself will be
        saved. N.B. each record is saved using a separate transaction, meaning
        that a failure to save this object will *not* roll back child saves.
    """
    sql_record = {}
    for key, value in self.iteritems():
      if isinstance(value, Record):
        if save_foreign:
          value.Save(save_foreign=True)
        sql_record[key] = value.key
      else:
        sql_record[key] = value

    if self.key is not None:
      self._RecordUpdate(sql_record)
    else:
      self._RecordInsert(sql_record)

  @classmethod
  def TableName(cls):
    """Returns the database table name for the Record class.

    If this is not explicitly defined by the class constant `_TABLE`, the return
    value will be the class name with the first letter lowercased.
    """
    if cls._TABLE:
      return cls._TABLE
    name = cls.__name__
    return name[0].lower() + name[1:]

  # Pylint falsely believes this property is overwritten by its setter later on.
  # pylint: disable=E0202
  @property
  def key(self):
    """Returns the primary key for the object.

    This is used for the Save/Update methods, where foreign relations should be
    stored by their primary key.
    """
    return self.get(self._PRIMARY_KEY)
  # pylint: enable=E0202

  # Pylint doesn't understand property setters at all.
  # pylint: disable=E0102, E0202, E1101
  @key.setter
  def key(self, value):
    """Sets the value of the primary key."""
    self[self._PRIMARY_KEY] = value
  # pylint: enable=E0102, E0202, E1101

  Error = Error
  AlreadyExistError = AlreadyExistError
  NotExistError = NotExistError
  PermissionError = PermissionError
