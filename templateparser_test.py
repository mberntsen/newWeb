#!/usr/bin/python2.5
"""Tests for the templateparser module."""
__author__ = 'janklopper@underdark.nl (Jan Klopper)'
__version__ = '0.3'

# Too many public methods
# pylint: disable-msg=R0904

# Standard modules
import unittest

# Unittest target
import templateparser as templateparser


class TemplateParserTags(unittest.TestCase):
  """Tests validity and parsing of simple tags."""
  def setUp(self):
    """Sets up a parser instance, as it never changes."""
    self.parser = templateparser.Parser()

  def testPlainTemplate(self):
    """Templates without tags get returned whole"""
    template = 'Template without any tags'
    self.assertEqual(template, self.parser.ParseString(template))

  def testSingleTagTemplate(self):
    """Templates with basic tags get returned proper"""
    template = 'Template with [single] tag'
    output = 'Template with just one tag'
    self.assertEqual(output, self.parser.ParseString(
        template, single='just one'))

  def testCasedTag(self):
    """Template tags may contain uppercase and lowercase or a mix thereof"""
    template = 'The parser has no trouble with [cAsE] case.'
    output = 'The parser has no trouble with mixed case.'
    self.assertEqual(output, self.parser.ParseString(template, cAsE='mixed'))

  def testUnderscoredTag(self):
    """Template tags may contains underscores as part of their name"""
    template = 'The template may contain [under_scored] tags.'
    output = 'The template may contain underscored tags.'
    self.assertEqual(output, self.parser.ParseString(
        template, under_scored='underscored'))

  def testMultiTagTemplate(self):
    """Templates with multiple (repeating) tags get parsed properly"""
    template = '[adjective] [noun] are better than other [noun].'
    output = 'Beefy cows are better than other cows.'
    self.assertEqual(output, self.parser.ParseString(
        template, noun='cows', adjective='Beefy'))

  def testBrokenTags(self):
    """Empty tags or tags containing whitespace are not actual tags"""
    template = 'This [ is a ] broken [] template, ][, really'
    self.assertEqual(template, self.parser.ParseString(
        template, **{' is a ': 'HORRIBLY', '': ', NASTY'}))

  def testBadCharacterTags(self):
    """Tags with bad characters are not considered tags"""
    bad_chars = """ :~!@#$%^&*()+-={}\|;':",./<>? """
    template = ''.join('[%s] [check]' % char for char in bad_chars)
    output = ''.join('[%s] ..' % char for char in bad_chars)
    replaces = dict((char, 'FAIL') for char in bad_chars)
    replaces['check'] = '..'
    self.assertEqual(output, self.parser.ParseString(template, **replaces))

  def testUnreplacedTag(self):
    """Template tags for which there is no replacement still exist in output"""
    template = 'Template with an [undefined] tag.'
    self.assertEqual(template, self.parser.ParseString(template))

  def testBracketsInsideTag(self):
    """The last opening bracket and first closing bracket are the delimiters"""
    template = 'Template tags may not contain [[spam] [eggs]].'
    output = 'Template tags may not contain [opening or closing brackets].'
    self.assertEqual(output, self.parser.ParseString(
        template, **{'[spam': 'EPIC', 'eggs]': 'FAIL',
                     'spam': 'opening or', 'eggs': 'closing brackets'}))


class TemplateParserIndexedTags(unittest.TestCase):
  """Tests the handling of complex tags (those with attributes/keys/indexes)."""
  def setUp(self):
    """Sets up a parser instance, as it never changes."""
    self.parser = templateparser.Parser()

  def testTemplateMappingKey(self):
    """Template tags can address mappings properly"""
    template = 'This uses a [dictionary:key].'
    output = 'This uses a spoon.'
    self.assertEqual(output, self.parser.ParseString(
        template, dictionary={'key': 'spoon'}))

  def testTemplateIndexing(self):
    """Template tags can access indexed iterables"""
    template = 'Template that grabs the [obj:2] key from the given tuple/list.'
    output = 'Template that grabs the third key from the given tuple/list.'
    numbers = 'first', 'second', 'third'
    self.assertEqual(output, self.parser.ParseString(template, obj=numbers))
    numbers = list(numbers)
    self.assertEqual(output, self.parser.ParseString(template, obj=numbers))

  def testTemplateAttributes(self):
    """Template tags will do attribute lookups, but only if 'by key' fails"""
    class Mapping(dict):
      """A subclass of a dictionary, so we can define attributes on it."""
      NAME = 'attribute'

    template = 'Template used [tag:NAME] lookup.'
    lookup_attr = 'Template used attribute lookup.'
    lookup_dict = 'Template used key (mapping) lookup.'

    mapp = Mapping()
    self.assertEqual(lookup_attr, self.parser.ParseString(template, tag=mapp))
    mapp['NAME'] = 'key (mapping)'
    self.assertEqual(lookup_dict, self.parser.ParseString(template, tag=mapp))

  def testTemplateMissingIndexes(self):
    """Complex tags with missing indexes (:index) will NOT be replaced"""
    class Object(object):
      """A simple object to store an attribute on."""
      NAME = 'Freeman'

    template = 'Hello [titles:1] [names:NAME], how is [names:other] [date:now]?'
    output = 'Hello [titles:1] Freeman, how is [names:other] [date:now]?'
    self.assertEqual(output, self.parser.ParseString(
        template, titles=['Mr'], names=Object(), date={}))

#  def testPerformance(self):
#    """Basic performance test for 2 template replacements"""
#    for i in range(100):
#      parser = templateparser.Parser()
#      template = 'This [obj:foo] is just a quick [bar]'
#      parser['example'] = template
#      for n in xrange(10):
#        parser.Parse('example', obj={'foo':'text'}, bar='hack')

class TemplateParserFunctions(unittest.TestCase):
  """Tests the functions that are performed on replaced tags."""
  def setUp(self):
    """Sets up a parser instance, as it never changes."""
    self.parser = templateparser.Parser()

  def testPipedFunctionUse(self):
    """Piped functions do not break the parser"""
    template = 'This function does [none|raw].'
    output = 'This function does "nothing".'
    self.assertEqual(output, self.parser.ParseString(
        template, none='"nothing"'))

  def testDefaultHtmlEscapeFunction(self):
    """The default function escapes HTML entities, and works properly"""
    template_default = 'This function does [none].'
    template_escape = 'This function does [none|html].'
    output = 'This function does &quot;nothing&quot;.'
    self.assertEqual(output, self.parser.ParseString(
        template_default, none='"nothing"'))
    self.assertEqual(output, self.parser.ParseString(
        template_escape, none='"nothing"'))

  def testCustomFunction(self):
    """Custom functions added to the parser work as expected"""
    self.parser.RegisterFunction('twice', lambda x: x + ' ' + x)
    template = 'The following will be stated [again|twice].'
    output = 'The following will be stated twice twice.'
    self.assertEqual(output, self.parser.ParseString(template, again='twice'))

  def testMultipleFunctions(self):
    """Multiple functions can be piped after one another"""
    self.parser.RegisterFunction('len', len)
    self.parser.RegisterFunction('count', lambda x: '%s characters' % x)
    template = 'A replacement processed by two functions: [spam|len|count].'
    output = 'A replacement processed by two functions: 8 characters.'
    self.assertEqual(output, self.parser.ParseString(template, spam='ham&eggs'))

  def testFunctionSeparation(self):
    """Template functions are only called for fragments that require them"""
    fragments_received = []
    def TemplateFunction(string):
      fragments_received.append(string)
      return string

    self.parser.RegisterFunction('x', TemplateFunction)
    template = 'X only has [num|x] call, else it\'s [expletive] [noun|raw].'
    output = 'X only has one call, else it\'s horribly broken.'
    self.assertEqual(output, self.parser.ParseString(
        template, num='one', expletive='horribly', noun='broken'))
    self.assertEqual(1, len(fragments_received))


class TemplateUnicodeBehavior(unittest.TestCase):
  """TemplateParser handles Unicode gracefully."""
  def setUp(self):
    """Sets up a parser instance, as it never changes."""
    self.parser = templateparser.Parser()

  def testUnicodeInput(self):
    """TemplateParser can handle unicode objects on input, converts to utf8"""
    template = 'Underdark Web framework, also known as [name].'
    output = u'Underdark Web framework, also known as \xb5Web.'.encode('utf8')
    name = u'\xb5Web'
    self.assertEqual(output, self.parser.ParseString(template, name=name))

  def testCreoleTemplateParsing(self):
    """The Creole module's return of <unicode> doesn't break the parser"""
    from underdark.libs import creole
    self.parser.RegisterFunction('creole', creole.CreoleToHtml)
    template = 'Creole [expr|creole]!'
    output = 'Creole <p><strong>rocks</strong> \xc2\xb5Web</p>\n!'
    self.assertEqual(output, self.parser.ParseString(
        template, expr=u'**rocks** \xb5Web'))

  def testTemplateFunctionReturnUnicode(self):
    """Template functions may return unicode objects, they are later encoded"""
    function_result = u'No more \N{BLACK HEART SUIT}'
    def TemplateFunction(_unused):
      return function_result

    self.parser.RegisterFunction('nolove', TemplateFunction)
    template = '[love|nolove]'
    output = function_result.encode('utf8')
    self.assertEqual(output, self.parser.ParseString(template, love='love'))


if __name__ == '__main__':
  unittest.main(testRunner=unittest.TextTestRunner(verbosity=2))
