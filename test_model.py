#!/usr/bin/python
"""Test suite for the database abstraction module (model)."""
__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '1.0'

# Too many public methods
# pylint: disable=R0904

# Standard modules
import unittest

# Unittest target
import model

# Necessary database backend
from underdark.libs.sqltalk import mysql


class BasicRecord(unittest.TestCase):
  """Tests for the Record class, a relational database record type."""
  class Author(model.Record):
    """Author class for testing purposes."""

  class Message(model.Record):
    """Simple message class."""

  def setUp(self):
    """Sets up the tests for the Record class."""
    self.connection = mysql.Connect('uweb_model_test', 'uweb_model_test')
    with self.connection as cursor:
      cursor.Execute('DROP TABLE IF EXISTS `author`')
      cursor.Execute('DROP TABLE IF EXISTS `message`')
      cursor.Execute("""CREATE TABLE `author` (
                            `ID` smallint(5) unsigned NOT NULL AUTO_INCREMENT,
                            `name` varchar(32) NOT NULL,
                            PRIMARY KEY (`ID`)
                          ) ENGINE=InnoDB  DEFAULT CHARSET=utf8""")
      cursor.Execute("""CREATE TABLE `message` (
                            `ID` smallint(5) unsigned NOT NULL AUTO_INCREMENT,
                            `author` smallint(5) unsigned NOT NULL,
                            `message` text NOT NULL,
                            PRIMARY KEY (`ID`)
                          ) ENGINE=InnoDB DEFAULT CHARSET=utf8""")

  def testLoadPrimary(self):
    """Database records can be loaded by primary key using FromPrimary()"""
    with self.connection as cursor:
      res = cursor.Insert(table='author', values={'name': 'King Arthur'})
      self.assertEqual(res.insertid, 1)  # First database record sanity check
    author = self.Author.FromPrimary(self.connection, 1)
    self.assertEqual(author.key, 1)
    self.assertEqual(author.key, author['ID'])
    self.assertEqual(author['name'], 'King Arthur')

  def testCreateRecord(self):
    """Database records can be created using Create()"""
    new_author = self.Author.Create(self.connection, {'name': 'King Arthur'})
    author = self.Author.FromPrimary(self.connection, new_author.key)
    self.assertEqual(author['name'], 'King Arthur')

  def testCreateRecordWithBadField(self):
    """Database record creation fails if there are unknown fields present"""
    self.assertRaises(model.BadFieldError, self.Author.Create, self.connection,
                      {'name': 'Bobby Tables', 'email': 'king@roundtable.com'})

  def testLoadRelated(self):
    """Fieldnames that match tablenames trigger automatic loading"""
    self.Author.Create(self.connection, {'name': 'King Arthur'})
    message = self.Message(self.connection, {'author': 1})
    self.assertEqual(type(message['author']), self.Author)
    self.assertEqual(message['author']['name'], 'King Arthur')
    self.assertEqual(message['author'].key, 1)

  def testLoadRelatedFailure(self):
    """Automatic loading raises NotExistError if the foreign record is absent"""
    message = self.Message(self.connection, {'author': 1})
    self.assertRaises(model.NotExistError, message.__getitem__, 'author')

  def testLoadRelatedSuppressedForNone(self):
    """Automatic loading is not attempted when the field value is `None`"""
    message = self.Message(self.connection, {'author': None})
    self.assertEqual(message['author'], None)

  def UpdateRecord(self):
    """The record can be given new values and these are properly stored"""
    self.assertTrue(False)

  def UpdatePrimaryKey(self):
    """Saving with an updated primary key properly saved the record"""
    # verify using len(list(Author.List()))
    self.assertTrue(False)


class VersionedRecord(unittest.TestCase):
  def setUp(self):
    """Sets up the tests for the VersionedRecord class."""
    self.connection = mysql.Connect('uweb_model_test', 'uweb_model_test')
    with self.connection as cursor:
      cursor.Execute('DROP TABLE IF EXISTS `versionedAuthor`')
      cursor.Execute('DROP TABLE IF EXISTS `versionedMessage`')
      cursor.Execute("""CREATE TABLE `versionedAuthor` (
                            `ID` smallint(5) unsigned NOT NULL AUTO_INCREMENT,
                            `authorID` smallint(5) unsigned NOT NULL,
                            `name` varchar(32) NOT NULL,
                            PRIMARY KEY (`ID`),
                            KEY `recordKey` (`authorID`)
                          ) ENGINE=InnoDB DEFAULT CHARSET=utf8""")
      cursor.Execute("""CREATE TABLE `versionedMessage` (
                            `ID` smallint(5) unsigned NOT NULL AUTO_INCREMENT,
                            `msgID` smallint(6) NOT NULL,
                            `author` smallint(5) unsigned NOT NULL,
                            `message` text NOT NULL,
                            PRIMARY KEY (`ID`)
                          ) ENGINE=InnoDB DEFAULT CHARSET=utf8""")


class CompoundKeyRecord(unittest.TestCase):
  pass


def Connection():
  connection = mysql.Connect('uweb_model_test', 'uweb_model_test')
  with connection as cursor:
    cursor.Execute('DROP TABLE IF EXISTS `author`')
    cursor.Execute('DROP TABLE IF EXISTS `message`')
    cursor.Execute('DROP TABLE IF EXISTS `versionedAuthor`')
    cursor.Execute('DROP TABLE IF EXISTS `versionedMessage`')
    cursor.Execute("""CREATE TABLE `author` (
                          `ID` smallint(5) unsigned NOT NULL AUTO_INCREMENT,
                          `name` varchar(32) NOT NULL,
                          PRIMARY KEY (`ID`)
                        ) ENGINE=InnoDB  DEFAULT CHARSET=utf8""")
    cursor.Execute("""CREATE TABLE `message` (
                          `ID` smallint(5) unsigned NOT NULL AUTO_INCREMENT,
                          `author` smallint(5) unsigned NOT NULL,
                          `message` text NOT NULL,
                          PRIMARY KEY (`ID`)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8""")
  return connection


if __name__ == '__main__':
  unittest.main(testRunner=unittest.TextTestRunner(verbosity=2))
