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
  _FOREIGN_KEY = None
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


  def __eq__(self, other):
    """Simple equality comparison for database objects.

    To compare equal, two objects must:
      1) Be of the same type;
      2) Have the same foreign key
      3) Have the same content.

    In the case that the compared objects have foreign relations, these  will be
    compared as well (recursively). If only one of the objects has foreign
    relations loaded, only the foreign key value will be compared to the value
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

  def __getitem__(self, field):
    """Returns the value corresponding to a given `field`.

    If a field represents a foreign key, this will be handled by `_LoadForeign`.
    """
    value = super(Record, self).__getitem__(field)
    return self._LoadForeign(field, value)

  def _GetChildren(self, child_class, relation_field=None):
    """Returns all `child_class` objects related to this record.

    The table for the given `child_class` will be queried for all fields where
    the `relation_field` is the same as this record's foreign key (`self.key`).

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

  def _LoadForeign(self, field, value):
    """Loads and returns objects referenced by foreign key.

    This is done by checking the `field` against the class' `_FOREIGN_RELATIONS`
    mapping. If a match is found the related class name will be resolved to a
    class (which should be a Record subclass) and the given `value` will be used
    to load an instance of that class using the `FromKey` classmethod.
    If the value for the field in `_FOREIGN_RELATIONS` is boolean False, no
    foreign relation will be resolved and `value` will be returned unchanged.

    If this fails, the `field` will be checked against table names for each
    of the subclasses that exist for the Record object (`_SUBTYPES`). If a match
    is found, an instance of the corresponding class will similarly be returned.

    If the `field` is not present in either mapping, its value will be returned
    unchanged.

    In all cases, if a field represented a foreign relation, it will be saved
    as to not need lookup in the future.
    """
    if not isinstance(value, Record):
      if field in self._FOREIGN_RELATIONS:
        class_name = self._FOREIGN_RELATIONS[field]
        if not class_name:
          return value
        foreign_class = getattr(sys.modules[self.__module__], class_name)
        value = foreign_class.FromKey(self.connection, value)
      elif field in self._SUBTYPES:
        value = self._SUBTYPES[field].FromKey(self.connection, value)
      self[field] = value
    return value

  def __hash__(self):
    """Returns the hashed value of the key."""
    return hash(self.key)

  def __int__(self):
    """Returns the integer key value of the Record.

    For record objects where the foreign key value is not (always) an integer,
    this function will raise an error in the situations where it is not.
    """
    if not isinstance(self.key, (int, long)):
      # We should not truncate floating point numbers.
      # Nor turn strings of numbers into an integer.
      raise ValueError('The foreign key is not an integral number.')
    return self.key

  def _RecordInsert(self, sql_record):
    """Inserts the given `sql_record` into the database.

    The table used to store this record is gathered from the `self.TableName()`
    property.
    Upon success, the record's foreign key is set to the result's insertid
    """
    with self.connection as cursor:
      record = cursor.Insert(table=self.TableName(), values=sql_record)
    self.key = record.insertid

  def _RecordUpdate(self, sql_record):
    """Updates the existing database entry with values from `sql_record`.

    The table used to store this record is gathered from the `self.TableName()`
    property. The condition with which the record is updated is the name and
    value of the Record's foreign key (`self._FOREIGN_KEY` and `self.key` resp.)
    """
    with self.connection as cursor:
      safe_key = self.connection.EscapeValues(self.key)
      cursor.Update(table=self.TableName(), values=sql_record,
                    conditions='`%s` = %s' % (self._FOREIGN_KEY, safe_key))

  @classmethod
  def DeleteKey(cls, connection, fkey_value):
    """Deletes a database record based on the foreign key value.

    Arguments:
      @ connection: sqltalk.connection
        Database connection to use.
      @ fkey_value: obj
        The value for the foreign key field

    Raises:
      ValueError
        If no _FOREIGN_KEY fieldname static variable is defined.
    """
    if cls._FOREIGN_KEY is None:
      raise ValueError(
          'Cannot delete a %r without _FOREIGN_KEY defined.' % cls.__name__)
    with connection as cursor:
      safe_key = connection.EscapeValues(fkey_value)
      cursor.Delete(table=cls.TableName(),
                    conditions='`%s` = %s' % (cls._FOREIGN_KEY, safe_key))

  @classmethod
  def FromKey(cls, connection, fkey_value):
    """Returns the Record object that belongs to the given foreign key value.

    Arguments:
      @ connection: sqltalk.connection
        Database connection to use.
      @ fkey_value: obj
        The value for the foreign key field

    Raises:
      NotExistError:
        There is no Record for that foreign key value.
      ValueError
        If no _FOREIGN_KEY fieldname static variable is defined.

    Returns:
      Record: Database record abstraction class.
    """
    if cls._FOREIGN_KEY is None:
      raise ValueError(
          'Cannot load a %r without _FOREIGN_KEY defined.' % cls.__name__)
    with connection as cursor:
      safe_key = connection.EscapeValues(fkey_value)
      record = cursor.Select(
          table=cls.TableName(),
          conditions='`%s` = %s' % (cls._FOREIGN_KEY, safe_key))
    if not record:
      raise NotExistError('There is No %r with key %r' % (
          cls.__name__, fkey_value))
    return cls(connection, record[0])

  def Delete(self):
    """Deletes a loaded record based on `self.TableName` and `self.key`.

    For deleting an unloaded object, use the classmethod `DeleteKey`.
    """
    with self.connection as cursor:
      cursor.Delete(table=self.TableName(), conditions='`%s` = %s' % (
          self._FOREIGN_KEY, self.connection.EscapeValues(self.key)))

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
    record class contained by the record is reduced to that record's foreign key
    (by use of the `key` property). If flagged to do so, it is at this point
    that the foreign record will be recursively `Save()`d.

    Once the clean `sql_record` is obtained, a check is performed to see whether
    the object should be inserted into the database, or updated there.
    This is done by checking the value of the record's own foreign key.

    If the `_FOREIGN_KEY` constant is not defined, the class is considered
    incomplete and any call to Save() will directly result in a ValueError.

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
    if self._FOREIGN_KEY is None:
      raise ValueError('Cannot Save() record without _FOREIGN_KEY defined.')

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
    """Returns the (unique) foreign key for the object.

    This is used for the Save/Update methods, where foreign relations should be
    stored by their foreign key.
    """
    if self._FOREIGN_KEY:
      return self.get(self._FOREIGN_KEY)
  # pylint: enable=E0202

  # Pylint doesn't understand property setters at all.
  # pylint: disable=E0102, E0202, E1101
  @key.setter
  def key(self, value):
    """Sets the value of the foreign key constraint."""
    self[self._FOREIGN_KEY] = value
  # pylint: enable=E0102, E0202, E1101

  Error = Error
  AlreadyExistError = AlreadyExistError
  NotExistError = NotExistError
  PermissionError = PermissionError
