#!/usr/bin/python
"""uWeb model base classes."""
from __future__ import with_statement

__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.2'


class Model(object):
  ID_FIELD = 'ID'  #XXX(Elmer): Could dump this in favor of the prikey field?
  RECORD_CLASS = Record
  TABLE = 'subclass_defined'

  def __init__(self, connection):
    self.connection = connection
    self._fields = []
    with self.connection as cursor:
      for row in cursor.Execute('EXPLAIN %s' % self.TABLE):
        self._fields.append(row)

  def _SelectNaiveRecords(self, **sqltalk_options):
    with self.connection as cursor:
      records = cursor.Select(table=self.TABLE, **sqltalk_options)
    for record in records:
      yield self.RECORD_CLASS(record)

  def GetById(self, record_id):
    conditions = '%s = %s' % (self.ID_FIELD,
                              self.connection.EscapeValues(record_id))
    return self._SelectNaiveRecords(conditions=conditions).next()


class Record(dict):
  def __init__(self, record, fields=None):
    super(Record, self).__init__(record)
    #XXX(Elmer): Can use these fields to validate data @ Save() time.
    # A record with inappropriate NULLs can be rejected.
    self._fields = fields
