#!/usr/bin/python2.5
"""Tests for the request module."""
__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '0.1'

# Method could be a function
# p-ylint: disable-msg=R0201

# Too many public methods
# p-ylint: disable-msg=R0904

# Standard modules
import cStringIO
import unittest

# Unittest target
import request


class IndexedFieldStorageTest(unittest.TestCase):
  """Comprehensive testing of the IndexedFieldStorage object."""

  def CreateFieldStorage(self, data):
    """Returns an IndexedFieldStorage object constructed from the given data."""
    return request.IndexedFieldStorage(cStringIO.StringIO(data),
                                       environ={'REQUEST_METHOD': 'POST'})

  def testEmptyStorage(self):
    """An empty IndexedFieldStorage is empty and is boolean False"""
    ifs = self.CreateFieldStorage('')
    self.assertFalse(ifs)

  def testBasicStorage(self):
    """A basic IndexedFieldStorage has the proper key + value pair"""
    ifs = self.CreateFieldStorage('key=value')
    self.assertTrue(ifs)
    self.assertEqual(ifs.getfirst('key'), 'value')
    self.assertEqual(ifs.getlist('key'), ['value'])

  def testMissingKey(self):
    """Getfirst / getlist for missing keys return proper defaults"""
    ifs = self.CreateFieldStorage('')
    self.assertEqual(ifs.getfirst('missing'), None)
    self.assertEqual(ifs.getfirst('missing', 'signal'), 'signal')
    self.assertEqual(ifs.getlist('missing'), [])
    # getlist has no default argument

if __name__ == '__main__':
  unittest.main(testRunner=unittest.TextTestRunner(verbosity=2))
