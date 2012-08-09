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


class BaseRecordTests(unittest.TestCase):
  """Offline tests of methods and behavior of the BaseRecord class."""
  def setUp(self):
    """Sets up the tests for the offline Record test."""
    class Writer(model.Record):
      """Test record for offline tests."""
    self.record_class = Writer

  def testTableName(self):
    """TableName returns the expected value and obeys _TABLE"""
    self.assertEqual(self.record_class.TableName(), 'writer')
    self.record_class._TABLE = 'author'
    self.assertEqual(self.record_class.TableName(), 'author')

  def testPrimaryKey(self):
    """Primary key defaults to 'ID' and changes to _PRIMARY_KEY are followed"""
    self.record = self.record_class(None, {'ID': 12, 'name': 'Tolkien'})
    self.assertEqual(self.record.key, 12)
    # Change the primary key and key will return the corresponding value
    self.record_class._PRIMARY_KEY = 'name'
    self.assertEqual(self.record.key, 'Tolkien')

  def testEquality(self):
    """Records of the same content are equal to eachother"""
    record_one = self.record_class(None, {'ID': 2, 'name': 'Rowling'})
    record_two = self.record_class(None, {'ID': 2, 'name': 'Rowling'})
    record_three = self.record_class(None, {'ID': 3, 'name': 'Rowling'})
    record_four = self.record_class(None, {'ID': 2, 'name': 'Rowling', 'x': 2})
    self.assertFalse(record_one is record_two)
    self.assertEqual(record_one, record_two)
    self.assertNotEqual(record_one, record_three)
    self.assertNotEqual(record_one, record_four)


class RecordTests(unittest.TestCase):
  """Online tests of methods and behavior of the Record class."""
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
      res = cursor.Insert(table='author', values={'name': 'Shakespeare'})
      self.assertEqual(res.insertid, 1)  # First database record sanity check
    author = self.Author.FromPrimary(self.connection, res.insertid)
    self.assertEqual(type(author), self.Author)      # Result is of correct type
    self.assertEqual(author.key, res.insertid)       # Primary key is set
    self.assertEqual(author['name'], 'Shakespeare')  # Name value is correct
    self.assertEqual(len(author), 2)                 # No additional fields
    # Another test with a non-autoincremented primary field
    with self.connection as cursor:
      res = cursor.Insert(table='author', values={'ID': 300, 'name': 'Seuss'})
      self.assertEqual(res.insertid, 300)  # Primary key value sanity check
    bobby = self.Author.FromPrimary(self.connection, res.insertid)
    self.assertEqual(bobby['name'], 'Seuss')

  def testCreateRecord(self):
    """Database records can be created using Create()"""
    new_author = self.Author.Create(self.connection, {'name': 'Chrstie'})
    author = self.Author.FromPrimary(self.connection, new_author.key)
    self.assertEqual(author['name'], 'Chrstie')

  def testCreateRecordWithBadField(self):
    """Database record creation fails if there are unknown fields present"""
    self.assertRaises(model.BadFieldError, self.Author.Create, self.connection,
                      {'name': 'Tolstoy', 'email': 'leo@tolstoy.ru'})

  def testLoadRelated(self):
    """Fieldnames that match tablenames trigger automatic loading"""
    self.Author.Create(self.connection, {'name': 'Koontz'})
    message = self.Message(self.connection, {'author': 1})
    self.assertEqual(type(message['author']), self.Author)
    self.assertEqual(message['author']['name'], 'Koontz')
    self.assertEqual(message['author'].key, 1)

  def testLoadRelatedFailure(self):
    """Automatic loading raises NotExistError if the foreign record is absent"""
    message = self.Message(self.connection, {'author': 1})
    self.assertRaises(model.NotExistError, message.__getitem__, 'author')

  def testLoadRelatedSuppressedForNone(self):
    """Automatic loading is not attempted when the field value is `None`"""
    message = self.Message(self.connection, {'author': None})
    self.assertEqual(message['author'], None)

  def testUpdateRecord(self):
    """The record can be given new values and these are properly stored"""
    author = self.Author.Create(self.connection, {'name': 'King Arthur'})
    author['name'] = 'Stephen King'
    author.Save()
    same_author = self.Author.FromPrimary(self.connection, 1)
    self.assertEqual(same_author['name'], 'Stephen King')
    self.assertEqual(same_author, author)

  def testUpdatePrimaryKey(self):
    """Saving with an updated primary key properly saved the record"""
    author = self.Author.Create(self.connection, {'name': 'Dickens'})
    self.assertEqual(author.key, 1)
    author['ID'] = 101
    author.Save()
    self.assertRaises(model.NotExistError, self.Author.FromPrimary,
                      self.connection, 1)
    same_author = self.Author.FromPrimary(self.connection, 101)
    self.assertEqual(same_author, author)


class VersionedRecordTests(unittest.TestCase):
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


class CompoundKeyRecordTests(unittest.TestCase):
  pass


if __name__ == '__main__':
  unittest.main(testRunner=unittest.TextTestRunner(verbosity=2))
