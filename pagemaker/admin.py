#!/usr/bin/python
"""Underdark uWeb PageMaker Mixins for admin purposes."""
from __future__ import with_statement

__author__ = 'Jan Klopper <jan@underdark.nl>'
__version__ = '0.1'

import os
import datetime
import decimal
import types

from uweb import templateparser
from uweb import model

ALLOWED_CLASS_TYPES = [model.VersionedRecord, model.Record]
NOT_ALLOWED_METHODS = dir({}) + ['key', 'record_key']

FIELDTYPES = {'datetime':datetime.datetime,
              'decimal':decimal.Decimal}

class AdminMixin(object):
  """Provides an admin interface based on the available models"""

  def _Admin(self, url):
    self.parser.RegisterFunction('items', lambda d: d.items())
    self.parser.RegisterFunction('classname', lambda cls: type(cls).__name__)

    if not self.ADMIN_MODEL:
      return 'Setup ADMIN_MODEL first'
    indextemplate = templateparser.FileTemplate(
      os.path.join(os.path.dirname(__file__), 'admin', 'index.html'))

    urlparts = (url or '').split('/')
    table = None
    method = 'List'
    methods = None
    results = None
    columns = None
    basepath = self.__BasePath()
    resultshtml = []
    columns = None
    edithtml = None
    message = None
    docs = None
    if len(urlparts) > 2:
      if urlparts[1] == 'table':
        table = urlparts[2]
        methods = self.__AdminTablesMethods(table)
        if len(urlparts) > 3:
          method = urlparts[3]
          if method == 'edit':
            edithtml = self.__EditRecord(table, urlparts[4])
          elif method == 'delete':
            key = self.post.getfirst('key')
            if self.__DeleteRecord(table, key):
              message = '%s with key %s deleted.' %(table, key)
            else:
              message = 'Could not find %s with key %s.' %(table, key)
          elif method == 'save':
            message = self.__SaveRecord(table, self.post.getfirst('key'))
        else:
          (columns, results) = self.__AdminTablesMethodsResults(urlparts[2],
                                                                method)

          resulttemplate = templateparser.FileTemplate(
              os.path.join(os.path.dirname(__file__), 'admin', 'record.html'))

          for result in results:
            resultshtml.append(resulttemplate.Parse(result=result['result'],
                                                    key=result['key'],
                                                    table=table,
                                                    basepath=basepath,
                                                    fieldtypes=FIELDTYPES))
      elif urlparts[1] == 'method':
        table = urlparts[2]
        methods = self.__AdminTablesMethods(table)
        docs = self.__GetDocs(table, urlparts[3])
    return indextemplate.Parse(basepath=basepath,
                               tables=self.__AdminTables(),
                               table=table,
                               columns=columns,
                               method=method,
                               methods=methods,
                               results=resultshtml,
                               edit=edithtml,
                               message=message,
                               docs=docs)

  def __GetDocs(self, table, method):
    if self.__CheckTable(table):
      table = getattr(self.ADMIN_MODEL, table)
      methodobj = getattr(table, method)
      if methodobj.__doc__:
        return methodobj.__doc__
      else:
        while table:
          table = table.__bases__[0]
          methodobj = getattr(table, method)
          if methodobj.__doc__:
            return methodobj.__doc__
        return 'no docs avaiable'

  def __EditRecord(self, table, key):
    self.parser.RegisterFunction('items', lambda d: d.items())
    self.parser.RegisterFunction('classname', lambda cls: type(cls).__name__)
    edittemplate = templateparser.FileTemplate(
        os.path.join(os.path.dirname(__file__), 'admin', 'edit.html'))
    fields = self.__EditRecordFields(table, key)
    if not fields:
      return 'Could not load record with %s' % key
    return edittemplate.Parse(table=table,
                              key=key,
                              basepath=self.__BasePath(),
                              fields=fields,
                              fieldtypes=FIELDTYPES)

  def __SaveRecord(self, table, key):
    if self.__CheckTable(table):
      table = getattr(self.ADMIN_MODEL, table)
      try:
        obj = table.FromPrimary(self.connection, key)
      except model.NotExistError:
        return 'Could not load record with %s' % key
      for item in obj.keys():
        if (isinstance(obj[item], int) or
          isinstance(obj[item], long)):
          obj[item] = int(self.post.getfirst(item, 0))
        elif (isinstance(obj[item], float) or
              isinstance(obj[item], decimal.Decimal)):
          obj[item] = float(self.post.getfirst(item, 0))
        elif isinstance(obj[item], basestring):
          obj[item] = self.post.getfirst(item, '')
        elif isinstance(obj[item], datetime.datetime):
          obj[item] = self.post.getfirst(item, '')
        else:
          obj[item] = int(self.post.getfirst(item, 0))
      try:
        obj.Save()
      except Exception, error:
        return error
      return 'Changes saved'
    return 'Invalid table'

  def __DeleteRecord(self, table, key):
    if self.__CheckTable(table):
      table = getattr(self.ADMIN_MODEL, table)
      try:
        obj = table.FromPrimary(self.connection, key)
        obj.Delete()
        return True
      except model.NotExistError:
        return False
    return False

  def __BasePath(self):
    return self.req.env['PATH_INFO'].split('/')[1]

  def __EditRecordFields(self, table, key):
    if self.__CheckTable(table):
      table = getattr(self.ADMIN_MODEL, table)
      try:
        return table.FromPrimary(self.connection, key)
      except model.NotExistError:
        return False
    return False

  def __CheckTable(self, table):
    if (not table.startswith('__')):
      for allowed_class in ALLOWED_CLASS_TYPES:
        tableclass = getattr(self.ADMIN_MODEL, table)
        try:
          if issubclass(tableclass, allowed_class):
            return True
        except TypeError:
          pass
    return False

  def __AdminTables(self):
    tables = []
    for table in dir(self.ADMIN_MODEL):
      if self.__CheckTable(table):
        tables.append(table)
    return tables

  def __AdminTablesMethods(self, table):
    if self.__CheckTable(table):
      table = getattr(self.ADMIN_MODEL, table)
      methods = []
      for method in dir(table):
        methodobj = getattr(table, method)
        if (not method.startswith('_') and
            method not in NOT_ALLOWED_METHODS and
            isinstance(methodobj, types.MethodType)):
          methods.append(method)
      return methods
    return False

  def __AdminTablesMethodsResults(self, tablename, methodname='List'):
    if self.__CheckTable(tablename):
      table = getattr(self.ADMIN_MODEL, tablename)
      method = getattr(table, methodname)
      results = method(self.connection)
      resultslist = []
      for result in results:
        resultslist.append({'result':result.values(),
                            'key':result.key})

      return (result.keys(), resultslist)
    return False
