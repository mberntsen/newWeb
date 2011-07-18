#!/usr/bin/python
"""uWeb model base classes."""
from __future__ import with_statement

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.5'


class Record(dict):
  """Basic class for database table/record abstraction."""
  _FOREIGN_KEY = None
  _TABLE = None

  def __init__(self, connection, record, load_foreign=True):
    """Initializes a Record instance.

    Arguments:
      @ connection: sqltalk.connection
        The database connection to use for further queries.
      @ record: dict / sqltalk.ResultSet
        A field-based mapping of the database record information.
      % load_foreign: bool ~~ True
        Flags loading of foreign key objects for the resulting Repository.
    """
    super(Record, self).__init__(record)
    self.connection = connection
    if load_foreign:
      self._LoadForeignRelations()

  def __eq__(self, other):
    """Simple equality comparison for database objects.

    Objects should be of same type, and have the same foreign key. Checking deep
    data is unreliable because the other object may not have its foreign
    relations loaded.
    """
    return (self.__class__ == other.__class__
            and self.key is not None
            and self.key == other.key)

  def __hash__(self):
    return self.key

  def _LoadForeignRelations(self):
    """Automatically loads objects references by foreign key.

    This should be implemented by subclasses where required.
    """

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
      cursor.Update(table=self.TableName(), values=sql_record,
                    conditions='%s=%s' % (self._FOREIGN_KEY, self.key))

  @classmethod
  def FromKey(cls, connection, fkey_id):
    """Returns the Record object that belongs to the given foreign key value.

    Arguments:
      @ connection: sqltalk.connection
        Database connection to use.
      @ fkey_id: obj
        The value for the foreign key field

    Raises:
      NotExistError:
        There is no Record for that foreign key value.

    Returns:
      Record: Datbase record abstraction class.
    """
    if cls._FOREIGN_KEY is None:
      raise ValueError(
          'Cannot load %s without _FOREIGN_KEY defined.' % cls.__name__)

    with connection as cursor:
      record = cursor.Select(table=cls.TableName(),
                             conditions='%s=%d' % (cls._FOREIGN_KEY, fkey_id))
    if not record:
      raise NotExistError('No %s with foreign key %s=%s' % (
          self.__class__.__name__, cls._FOREIGN_KEY, fkey_id))
    return cls(connection, record[0])

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
