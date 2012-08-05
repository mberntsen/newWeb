#!/usr/bin/python
"""uWeb model base classes."""
from __future__ import with_statement

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.17'

# Standard modules
import datetime
import simplejson
import sys


class Error(Exception):
  """Superclass used for inheritance and external exception handling."""


class AlreadyExistError(Error):
  """The resource already exists, and cannot be created twice."""


class NotExistError(Error):
  """The requested or provided resource doesn't exist or isn't accessible."""


class PermissionError(Error):
  """The entity has insufficient rights to access the resource."""


# Record classes have many methods, this is not an actual problem.
# pylint: disable=R0904
class BaseRecord(dict):
  """Basic database record wrapping class.

  This allows structured database manipulation for applications. Supported
  features include:
  * Loading a record from Primary Key;
  * Deleting a record by Primary Key;
  * Deleting an existing open record;
  * Listing all records of the current type;
  * Calculating the minimum changed set and storing this to the database.
  """
  _PRIMARY_KEY = 'ID'
  _TABLE = None

  def __init__(self, connection, record, run_init_hook=True):
    """Initializes a BaseRecord instance.

    Arguments:
      @ connection: object
        The database connection to use for further queries.
      @ record: mapping
        A field:value mapping of the database record information.
      % run_init_hook: bool ~~ True
        States whether or not the `_PostInit()` hook should be run after
        the other initialization steps have completed.
    """
    super(BaseRecord, self).__init__(record)
    if not hasattr(BaseRecord, '_SUBTYPES'):
      # Adding classes at runtime is pretty rare, but fails this code.
      BaseRecord._SUBTYPES = dict(RecordTableNames())
    self.connection = connection
    self._record = self._DataRecord()
    # _PostInit hook should run after making a live copy of the data, so that
    # mirrored data transforms between _PostInit and _PreSave will not trigger
    # the record to be updated on saves where the data hasn't actually changed.
    if run_init_hook:
      self._PostInit()

  def __eq__(self, other):
    """Simple equality comparison for database objects.

    To compare equal, two objects must:
      1) Be of the same type;
      2) Have the same primary key which is NOT None;
      3) Have the same content.

    In the case that the compared objects have foreign relations, these  will be
    compared as well (recursively). If only one of the objects has foreign
    relations loaded, only the primary key value will be compared to the value
    in the other Record.
    """
    if type(self) != type(other):
      return False  # Types must be the same.
    elif not (self.key == other.key is not None):
      return False  # Records should have the same non-None primary key value.
    elif len(self) != len(other):
      return False  # Records must contain the same number of objects.
    for key, value in self.items():
      other_value = other[key]
      if isinstance(value, BaseRecord) != isinstance(other_value, BaseRecord):
        # Only one of the two is a BaseRecord instance
        if (isinstance(value, BaseRecord) and value.key != other_value or
            isinstance(other_value, BaseRecord) and other_value.key != value):
          return False
      elif value != other_value:
        return False
    return True

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

  def __ne__(self, other):
    """Returns the proper inverse of __eq__."""
    # Without this, the non-equal checks used in __eq__ will not work,
    # and the  `!=` operator would not be the logical inverse of `==`.
    return not self == other

  def __repr__(self):
    return '%s(%s)' % (type(self).__name__, super(BaseRecord, self).__repr__())

  def __str__(self):
    return '%s({%s})' % (
        self.__class__.__name__,
        ', '.join('%r: %r' % item for item in self.iteritems()))

  # ############################################################################
  # Rich comparators
  #
  def __gt__(self, other):
    """Index of this record is greater than the other record's.

    This requires both records to be of the same record class."""
    if type(self) == type(other):
      return self.key > other.key
    return NotImplemented

  def __ge__(self, other):
    """Index of this record is greater than, or equal to, the other record's.

    This requires both records to be of the same record class."""
    if type(self) == type(other):
      return self.key >= other.key
    return NotImplemented

  def __lt__(self, other):
    """Index of this record is smaller than the other record's.

    This requires both records to be of the same record class."""
    if type(self) == type(other):
      return self.key < other.key
    return NotImplemented

  def __le__(self, other):
    """Index of this record is smaller than, or equal to, the other record's.

    This requires both records to be of the same record class."""
    if type(self) == type(other):
      return self.key <= other.key
    return NotImplemented

  # ############################################################################
  # Hooks for things to run before and after creating and updating records
  #
  def _PreCreate(self, _cursor):
    """Hook that runs before creating (inserting) a Record in the database.

    Typically you would verify values of the Record in this step, or transform
    the data for database-safe insertion. If the data is transformed here, this
    transformation should be reversed in `_PostCreate()`.
    """

  def _PreSave(self, _cursor):
    """Hook that runs before saving (updating) a Record in the database.

    Typically you would verify values of the Record in this step, or transform
    the data for database-safe insertion. If the data is transformed here, this
    transformation should be reversed in `_PostSave()`.
    """

  def _PostInit(self):
    """Hook that runs after initializing a Record instance.

    This typically runs on every instance, but can be suppressed. Records that
    are newly created using the `Create()` classmethod will NOT have this hook
    run. They should use `_PreCreate()` and `_PostCreate()` methods.

    Any transforms done after creating and saving should likely be present here.
    """

  def _PostCreate(self, _cursor):
    """Hook that runs after creating (inserting) a Record in the database.

    Any transforms that were performed on the data should be reversed here.
    """

  def _PostSave(self, _cursor):
    """Hook that runs after saving (updating) a Record in the database.

    Any transforms that were performed on the data should be reversed here.
    """

  # ############################################################################
  # Base record functionality methods, to be implemented by subclasses.
  # Some methods have a generic implementation, but may need customization,
  #
  @classmethod
  def Create(cls, connection, record):
    """Creates a proper record object and stores it to the database.

    After storing it to the database, the live object is returned

    Arguments:
      @ connection: object
        Database connection to use for the created record..
      @ record: mapping
        The record data to write to the database.

    Returns:
      BaseRecord: the record that was created from the initiation mapping.
    """
    raise NotImplementedError

  @classmethod
  def DeletePrimary(cls, connection, key):
    """Deletes a database record based on the primary key value.

    Arguments:
      @ connection: object
        Database connection to use.
      @ pkey_value: obj
        The value for the primary key field
    """
    raise NotImplementedError

  def Delete(self):
    """Deletes a loaded record based on `self.TableName` and `self.key`.

    For deleting an unloaded object, use the classmethod `DeletePrimary`.
    """
    self.DeletePrimary(self.connection, self.key)
    self._record.clear()
    self.clear()

  @classmethod
  def FromPrimary(cls, connection, pkey_value):
    """Returns the Record object that belongs to the given primary key value.

    Arguments:
      @ connection: object
        Database connection to use.
      @ pkey_value: obj
        The value for the primary key field

    Raises:
      NotExistError:
        There is no record that matches the given primary key value.

    Returns:
      Record: Database record abstraction class.
    """
    raise NotImplementedError

  @classmethod
  def List(cls, connection, condition=None):
    """Yields a Record object for every table entry.

    Arguments:
      @ connection: object
        Database connection to use.
      % condition: str
        Optional query portion that will be used to limit the list of results

    Yields:
      Record: Database record abstraction class.
    """
    raise NotImplementedError

  def Save(self):
    """Saves the changes made to the record.

    This performs an update to the record, except when `create_new` if set to
    True, in which case the record is inserted.

    Arguments:
      % create_new: bool ~~ False
        Tells the method to create a new record instead of updating a current.
        This should be used when Save is called by the Create() method.
    """
    raise NotImplementedError


  # ############################################################################
  # Functions for tracking table and primary key values
  #
  def _Changes(self):
    """Returns the differences of the current state vs the last stored state."""
    sql_record = self._DataRecord()
    for key, value in sql_record.items():
      if self._record.get(key) == value:
        del sql_record[key]
    return sql_record

  def _DataRecord(self):
    """Returns a dictionary of the record's database values

    For any Record object present, its primary key value (`Record.key`) is used.
    """
    sql_record = {}
    for key, value in super(BaseRecord, self).iteritems():
      sql_record[key] = self._ValueOrPrimary(value)
    return sql_record

  @staticmethod
  def _ValueOrPrimary(value):
    """Returns the value, or its primary key value if it's a Record."""
    return value.key if isinstance(value, BaseRecord) else value

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
    if isinstance(self._PRIMARY_KEY, tuple):
      record = self._DataRecord()
      return tuple(record[key] for key in self._PRIMARY_KEY)
    return self.get(self._PRIMARY_KEY)
  # pylint: enable=E0202

  # Pylint doesn't understand property setters at all.
  # pylint: disable=E0102, E0202, E1101
  @key.setter
  def key(self, value):
    """Sets the value of the primary key."""
    if isinstance(value, tuple):
      if len(value) != len(self._PRIMARY_KEY):
        raise ValueError('Not enough values for compound key.')
      for key, key_val in zip(self._PRIMARY_KEY, value):
        self[key] = key_val
    else:
      self[self._PRIMARY_KEY] = value
  # pylint: enable=E0102, E0202, E1101

  Error = Error
  AlreadyExistError = AlreadyExistError
  NotExistError = NotExistError
  PermissionError = PermissionError


class Record(BaseRecord):
  """Extensions to the Record abstraction for relational database use."""
  _FOREIGN_RELATIONS = {}

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
    if not isinstance(value, BaseRecord):
      if field in self._FOREIGN_RELATIONS:
        return self._LoadUsingForeignRelations(
            self._FOREIGN_RELATIONS[field], field, value)
      elif field == self.TableName():
        return value
      elif field in self._SUBTYPES:
        value = self._SUBTYPES[field].FromPrimary(self.connection, value)
        self[field] = value
    return value

  def _LoadUsingForeignRelations(self, cls, field, value):
    """Loads and returns foreign relation based on given class (name).

    The action taken depends on the given `cls`. If the given class is None (or
    otherwise boolean false), no action will be taken, and the value will be
    returned unchanged.

    If the class is given as string, it will be loaded from the current module.
    It should be a proper subclass of Record, after which the current `value` is
    used to create a record using `cls.FromPrimary`.

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
    value = cls.FromPrimary(self.connection, value)
    self[field] = value
    return value

  # ############################################################################
  # Override basic dict methods so that autoload mechanisms function on them.
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
  @classmethod
  def _FromParent(cls, parent, relation_field=None, conditions=None):
    """Returns all `cls` objects that are a child of the given parent.

    This utilized the parent's _Children method, with either this class'
    TableName or the filled out `relation_field`.

    Arguments:
      @ parent: Record
        The parent for who children should be found in this class
      % relation_field: str ~~ cls.TableName()
        The fieldname in this class' table which relates to the parent's primary
        key. If not given, parent.TableName() will be used.
      % conditions: str / iterable ~~ None
        The extra condition(s) that should be applied when querying for records.
    """
    if not isinstance(parent, Record):
      raise TypeError('parent argument should be a Record type.')
    relation_field = relation_field or parent.TableName()
    relation_value = parent.connection.EscapeValues(parent.key)
    qry_conditions = ['`%s` = %s' % (relation_field, relation_value)]
    if isinstance(conditions, basestring):
      qry_conditions.append(conditions)
    elif conditions:
      qry_conditions.extend(conditions)
    return cls.List(parent.connection, conditions=qry_conditions)

  def _Children(self, child_class, relation_field=None, conditions=None):
    """Returns all `child_class` objects related to this record.

    The table for the given `child_class` will be queried for all fields where
    the `relation_field` is the same as this record's primary key (`self.key`).

    These records will then be yielded as instances of the child class.

    Arguments:
      @ child_class: type (Record subclass)
        The child class whose objects should be found.
      % relation_field: str ~~ self.TableName()
        The fieldname in the `child_class` table which relates that table to
        the table for this record.
      % conditions: str / iterable ~~
        The extra condition(s) that should be applied when querying for records.
    """
    # Delegating to let child class handle its own querying. These are methods
    # for development, and are private only to prevent name collisions.
    # pylint: disable=W0212
    return child_class._FromParent(
        self, relation_field=relation_field, conditions=conditions)

  def _DeleteChildren(self, child_class, relation_field=None):
    """Deletes all `child_class` objects related to this record.

    The table for the given `child_class` will be queried for all fields where
    the `relation_field` is the same as this record's primary key (`self.key`).

    Arguments:
      @ child_class: type (Record subclass)
        The child class whose objects should be deleted.
      % relation_field: str ~~ self.TableName()
        The fieldname in the `child_class` table which relates that table to
        the table for this record.
    """
    relation_field = relation_field or self.TableName()
    with self.connection as cursor:
      safe_key = self.connection.EscapeValues(self.key)
      cursor.Delete(table=child_class.TableName(),
                    conditions='`%s`=%s' % (relation_field, safe_key))

  @classmethod
  def _PrimaryKeyCondition(cls, connection, value):
    """Returns the MySQL primary key condition to be used."""
    if isinstance(value, tuple):
      if len(value) != len(cls._PRIMARY_KEY):
        raise ValueError('Not enough values for compound key.')
      values = map(cls._ValueOrPrimary, value)
      return ' AND '.join('`%s` = %s' % (field, value) for field, value
                   in zip(cls._PRIMARY_KEY, connection.EscapeValues(values)))
    else:
      return '`%s` = %s' % (cls._PRIMARY_KEY,
                            connection.EscapeValues(cls._ValueOrPrimary(value)))

  def _RecordCreate(self, cursor):
    """Inserts the record's current values in the database as a new record.

    Upon success, the record's primary key is set to the result's insertid
    """
    # Compound key case
    if isinstance(self._PRIMARY_KEY, tuple):
      values = self._DataRecord()
      auto_inc_field = set(self._PRIMARY_KEY) - set(values)
      if auto_inc_field:
        raise ValueError('No value for compound key field(s): %s' % (
            ', '.join(map(repr, auto_inc_field))))
      return cursor.Insert(table=self.TableName(), values=self._DataRecord())
    # Single-column key case
    result = cursor.Insert(table=self.TableName(), values=self._DataRecord())
    if result.insertid:
      self._record[self._PRIMARY_KEY] = self.key = result.insertid

  def _RecordUpdate(self, cursor):
    """Updates the existing database entry with the record's current values.

    The constraint with which the record is updated is the name and value of
    the Record's primary key (`self._PRIMARY_KEY` and `self.key` resp.)
    """
    try:
      if isinstance(self._PRIMARY_KEY, tuple):
        primary = tuple(self._record[key] for key in self._PRIMARY_KEY)
      else:
        primary = self._record[self._PRIMARY_KEY]
    except KeyError:
      raise Error('Cannot update record without pre-existing primary key.')
    cursor.Update(
        table=self.TableName(), values=self._Changes(),
        conditions=self._PrimaryKeyCondition(self.connection, primary))

  def _SaveForeign(self, cursor):
    """Recursively saves all nested Record instances."""
    for value in super(Record, self).itervalues():
      if isinstance(value, Record):
        # Accessing protected members of a foreign class. Also, the only means
        # of recursively saving the record tree without opening multiple
        # database transactions (which would lead to exceptions really fast).
        # pylint: disable=W0212
        value._SaveForeign(cursor)
        value._SaveSelf(cursor)

  def _SaveSelf(self, cursor):
    """Updates the existing database entry with the record's current values.

    The constraint with which the record is updated is the name and value of
    the Record's primary key (`self._PRIMARY_KEY` and `self.key` resp.)
    """
    difference = self._Changes()
    if difference:
      self._PreSave(cursor)
      self._RecordUpdate(cursor)
      self._PostSave(cursor)
      self._record.update(difference)

  # ############################################################################
  # Public methods for creation, deletion and storing Record objects.
  #
  @classmethod
  def Create(cls, connection, record):
    record = cls(connection, record, run_init_hook=False)
    with connection as cursor:
      # Accessing protected members of a foreign class.
      # pylint: disable=W0212
      record._PreCreate(cursor)
      record._RecordCreate(cursor)
      record._PostCreate(cursor)
    return record

  @classmethod
  def DeletePrimary(cls, connection, pkey_value):
    with connection as cursor:
      cursor.Delete(table=cls.TableName(),
                    conditions=cls._PrimaryKeyCondition(connection, pkey_value))

  @classmethod
  def FromPrimary(cls, connection, pkey_value):
    with connection as cursor:
      record = cursor.Select(
          table=cls.TableName(),
          conditions=cls._PrimaryKeyCondition(connection, pkey_value))
    if not record:
      raise NotExistError('There is no %r for primary key %r' % (
          cls.__name__, pkey_value))
    return cls(connection, record[0])

  @classmethod
  def List(cls, connection, conditions=None):
    with connection as cursor:
      records = cursor.Select(table=cls.TableName(), conditions=conditions)
    for record in records:
      yield cls(connection, record)

  # SQL Records have foreign relations, saving needs an extra argument for this.
  # pylint: disable=W0221
  def Save(self, save_foreign=False):
    """Saves the changes made to the record.

    This expands on the base Save method, providing a save_foreign that will
    recursively update all nested records when set to True.

    Arguments:
      % save_foreign: bool ~~ False
        If set, each Record (subclass) contained by this one will be saved as
        well. This recursive saving triggers *before* this record itself will be
        saved. N.B. each record is saved using a separate transaction, meaning
        that a failure to save this object will *not* roll back child saves.
    """
    with self.connection as cursor:
      if save_foreign:
        self._SaveForeign(cursor)
      self._SaveSelf(cursor)
    return self
  # pylint: enable=W0221


class VersionedRecord(Record):
  """Basic class for database table/record abstraction."""
  _RECORD_KEY = 'recordKey'

  # ############################################################################
  # Public methods for creation, deletion and storing Record objects.
  #
  @classmethod
  def FromIdentifier(cls, connection, identifier):
    """Returns the newest Record object that matches the given identifier.

    N.B. Newest is defined as 'last in lexicographical sort'.

    Arguments:
      @ connection: sqltalk.connection
        Database connection to use.
      @ identifier: obj
        The value of the record key field

    Raises:
      NotExistError:
        There is no Record that matches the given identifier.

    Returns:
      Record: The newest record for the given identifier.
    """
    safe_id = connection.EscapeValues(identifier)
    with connection as cursor:
      record = cursor.Select(
          table=cls.TableName(), limit=1, order=[(cls._PRIMARY_KEY, True)],
          conditions='`%s`=%s' % (cls._RECORD_KEY, safe_id))
    if not record:
      raise NotExistError('There is no %r for identifier %r' % (
          cls.__name__, identifier))
    return cls(connection, record[0])

  @classmethod
  def List(cls, connection, conditions=None):
    """Yields the latest Record for each versioned entry in the table.

    Arguments:
      @ connection: sqltalk.connection
        Database connection to use.

    Yields:
      Record: The Record with the newest version for each versioned entry.
    """
    if isinstance(conditions, (list, tuple)):
      conditions = ' AND '.join(conditions)
    with connection as cursor:
      records = cursor.Execute("""
          SELECT `%(table)s`.*
          FROM `%(table)s`
          JOIN (SELECT MAX(`%(primary)s`) AS `max`
                FROM `%(table)s`
                GROUP BY `%(record_key)s`) AS `versions`
              ON (`%(table)s`.`%(primary)s` = `versions`.`max`)
          WHERE %(conditions)s
          """ % {'primary': cls._PRIMARY_KEY,
                 'record_key': cls._RECORD_KEY,
                 'table': cls.TableName(),
                 'conditions': conditions or '1'})
    for record in records:
      yield cls(connection, record)

  @classmethod
  def ListVersions(cls, connection, identifier, conditions='1'):
    """Yields all versions for a given record identifier.

    Arguments:
      @ connection: sqltalk.connection
        Database connection to use.
      % conditions: str
        Optional query portion that will be used to limit the list of results

    Yields:
      Record: One for each stored version for the identifier.
    """
    if isinstance(conditions, (list, tuple)):
      conditions = ' AND '.join(conditions)
    safe_id = connection.EscapeValues(identifier)
    with connection as cursor:
      records = cursor.Select(table=cls.TableName(),
                              conditions='`%s` = %s AND %s' % (
                                  cls._RECORD_KEY, safe_id, conditions))
    for record in records:
      yield cls(connection, record)

  # ############################################################################
  # Private methods to control VersionedRecord behaviour
  #
  @classmethod
  def _NextRecordKey(cls, cursor):
    """Returns the next record key to use, the previous (or zero) plus one."""
    return (cls._MaxRecordKey(cursor) or 0) + 1

  @classmethod
  def _MaxRecordKey(cls, cursor):
    """Returns the currently largest record key value."""
    last_key = cursor.Select(table=cls.TableName(), fields=cls._RECORD_KEY,
                             order=[(cls._RECORD_KEY, True)], limit=1)
    if last_key:
      return last_key[0][0]

  def _PreCreate(self, cursor):
    """Attaches a RecordKey to the Record if it doens't have one already.

    Before we create a new record, we need to acquire the next-in-line RecordKey
    if none has been provided. If one has been provided, we'll use that one.
    """
    if self.record_key is None:
      self.record_key = self._NextRecordKey(cursor)

  def _PreSave(self, _cursor):
    """Before saving a record, reset the primary key value.

    This assures that we will not have a primary key conflict, though it does
    assume an AutoIncrement primary key field.
    """
    self.key = None

  def _RecordUpdate(self, cursor):
    """All updates are handled as new inserts for the same Record Key."""
    self._RecordCreate(cursor)

  # Pylint falsely believes this property is overwritten by its setter later on.
  # pylint: disable=E0202
  @property
  def record_key(self):
    """Returns the value of the version field of the record.

    This is used for the Save/Update methods, where foreign relations should be
    stored by their primary key.
    """
    return self.get(self._RECORD_KEY)
  # pylint: enable=E0202

  # Pylint doesn't understand property setters at all.
  # pylint: disable=E0102, E0202, E1101
  @record_key.setter
  def record_key(self, value):
    """Sets the value of the primary key."""
    self[self._RECORD_KEY] = value
  # pylint: enable=E0102, E0202, E1101


class MongoRecord(BaseRecord):
  """Abstraction of MongoDB collection records."""
  _PRIMARY_KEY = '_id'

  @classmethod
  def Collection(cls, connection):
    """Returns the collection that the MongoRecord resides in."""
    return getattr(connection, cls.TableName())

  @classmethod
  def Create(cls, connection, record):
    record = cls(connection, record, run_init_hook=False)
    # Accessing protected members of a foreign class.
    # pylint: disable=W0212
    record._PreCreate(None)
    record._StoreRecord()
    record._PostCreate(None)
    # pylint: enable=W0212
    return record

  @classmethod
  def DeletePrimary(cls, connection, pkey_value):
    collection = cls.Collection(connection)
    collection.remove({cls._PRIMARY_KEY: pkey_value})

  @classmethod
  def FromPrimary(cls, connection, pkey_value):
    from pymongo import objectid
    if not isinstance(pkey_value, objectid.ObjectId):
      pkey_value = objectid.ObjectId(pkey_value)
    collection = cls.Collection(connection)
    record = collection.find({cls._PRIMARY_KEY: pkey_value})
    if not record:
      raise NotExistError('There is no %r for primary key %r' % (
          cls.__name__, pkey_value))
    return cls(connection, record[0])

  @classmethod
  def List(cls, connection, conditions=None):
    for record in cls.Collection(connection).find(conditions or {}):
      yield cls(connection, record)

  def Save(self):
    changes = self._Changes()
    if changes:
      self._PreSave(None)
      self._StoreRecord()
      self._PostSave(None)
      self._record.update(changes)
    return self

  def _StoreRecord(self):
    self.key = self.Collection(self.connection).save(self._DataRecord())


class Smorgasbord(object):
  """A connection tracker for uWeb Record classes.

  The idea is that you can set up a Smorgasbord with various different
  connection types (Mongo and relational), and have the smorgasbord provide the
  correct connection for the caller's needs. MongoReceord would be given the
  MongoDB connection as expected, and all other users will be given a relational
  datbaase connection.

  This is highly beta and debugging is going to be at the very least interesting
  because of __getattribute__ overriding that is necessary for this type of
  behavior.
  """
  CONNECTION_TYPES = 'mongo', 'relational'

  def __init__(self, connections=None):
    self.connections = {} if connections is None else connections

  def AddConnection(self, connection, con_type):
    """Adds a connection and its type to the Smorgasbord.

    The connection type should be one of the strings defined in the class
    constant `CONNECTION_TYPES`.
    """
    if con_type not in self.CONNECTION_TYPES:
      raise ValueError('Unknown connection type %r' % con_type)
    self.connections[con_type] = connection

  def RelevantConnection(self):
    """Returns the relevant database connection dependant on the caller model.

    If the caller model cannot be determined, the 'relational' database
    connection is returned as a fallback method.
    """
    # Figure out caller type or instance
    # pylint: disable=W0212
    caller_locals = sys._getframe(2).f_locals
    # pylint: enable=W0212
    if 'self' in caller_locals:
      caller_cls = type(caller_locals['self'])
    else:
      caller_cls = caller_locals.get('cls', type)
    # Decide the type of connection to return for this caller
    if issubclass(caller_cls, MongoRecord):
      con_type = 'mongo'
    else:
      con_type = 'relational' # This is the default connection to return.
    try:
      return self.connections[con_type]
    except KeyError:
      raise TypeError('There is no connection for type %r' % con_type)

  def __enter__(self):
    """Proxies the transaction to the underlying relevant connection.

    This is not quite as transparent a passthrough as using __getattribute__,
    but it necessary due to performance optimizations done in Python2.7
    """
    return self.RelevantConnection().__enter__()

  def __exit__(self, *args):
    """Proxies the transaction to the underlying relevant connection.

    This is not quite as transparent a passthrough as using __getattribute__,
    but it necessary due to performance optimizations done in Python2.7
    """
    return self.RelevantConnection().__exit__(*args)

  def __getattribute__(self, attribute):
    try:
      # Pray to God we haven't overloaded anything from our connection classes.
      return super(Smorgasbord, self).__getattribute__(attribute)
    except AttributeError:
      return getattr(self.RelevantConnection(), attribute)


def RecordTableNames():
  """Yields Record subclasses that have been defined outside this module.

  This is necessary to accurately perform automatic loading of foreign elements.
  There is one requirement to this, and that's that all subclasses of Record
  are loaded in memory by the time the first Record is instantiated, because
  this function will only be called once by default.
  """
  def GetSubTypes(cls, seen=None):
    """Recursively and depth-first retrieve subclasses of a given type."""
    seen = seen or set()
    # Pylint mistakenly believes there is no method __subclasses__
    # pylint: disable=E1101
    for sub in cls.__subclasses__():
    # pylint: enable=E1101
      if sub not in seen:
        seen.add(sub)
        yield sub
        for sub in GetSubTypes(sub, seen):
          yield sub

  for cls in GetSubTypes(BaseRecord):
    # Do not yield subclasses defined in this module
    if cls.__module__ != __name__:
      yield cls.TableName(), cls


def RecordToDict(record, complete=False, recursive=False):
  """Returns a dictionary representation of the Record.

  Arguments:
    @ record: Record
      A record object that should be turned to a dictionary
    % complete: bool ~~ False
      Whether the foreign references on the object should all be resolved before
      converting the Record to a dictionary. Either way, existing resolved
      references will be represented as complete dictionaries.
    % recursive: bool ~~ False
      When this and `complete` are set True, foreign references will recursively
      be resolved, resulting in the entire tree to be expanded before it is
      converted to a dictionary.

    Returns:
      dict: dictionary representation of the record.
    """
  record_dict = {}
  record = record if complete else dict(record)
  for key, value in record.iteritems():
    if isinstance(value, Record):
      if complete and recursive:
        record_dict[key] = RecordToDict(value, complete=True, recursive=True)
      else:
        record_dict[key] = dict(value)
    else:
      record_dict[key] = value
  return record_dict


def MakeJson(record, complete=False, recursive=False):
  """Returns a JSON object string of the given `record`.

  Before turning the record into a JSON object, it is passed through
  RecordToDict(). The arguemnts `complete` and `recursive` function to those
  on that function.

  Additional conversion will be done for types  such as datetime `datetime`,
  `time`, and `date`.

  Returns:
    str: JSON representation of the given record dictionary.
  """
  def _Encode(obj):
    if isinstance(obj, datetime.datetime):
      return obj.strftime('%F %T')
    if isinstance(obj, datetime.date):
      return obj.strftime('%F')
    if isinstance(obj, datetime.time):
      return obj.strftime('%T')

  if isinstance(record, Record):
    record = RecordToDict(complete=complete, recursive=recursive)
  return simplejson.dumps(record, default=_Encode, sort_keys=True)
