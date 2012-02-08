#!/usr/bin/python2.5
"""Tests for the templateparser module."""
__author__ = 'Elmer de Looff <elmer@underdark.nl>'
__version__ = '1.2'

# Too many public methods
# pylint: disable=R0904

# Standard modules
import os
import unittest

# Unittest target
import templateparser as templateparser


class Parser(unittest.TestCase):
  """Basic tests for the Parser class and equality of Template objects."""
  def setUp(self):
    """Creates a template file and a similar instance attribute."""
    self.name = 'tmp_template'
    self.raw = 'This is a basic [noun]'
    self.template = templateparser.Template(self.raw)
    with file(self.name, 'w') as template:
      template.write('This is a basic [noun]')
      template.flush()

  def tearDown(self):
    """Removes the template file from the filesystem."""
    os.unlink('tmp_template')

  def testAddTemplate(self):
    """[Parser] AddTemplate adds a template to the parser"""
    parser = templateparser.Parser()
    self.assertEqual(0, len(parser))
    parser.AddTemplate(self.name)
    self.assertEqual(1, len(parser))
    self.assertEqual(self.template, parser[self.name])

  def testAccessTemplate(self):
    """[Parser] getting a template by key loads it when required"""
    parser = templateparser.Parser()
    self.assertEqual(0, len(parser))
    self.assertEqual(self.template, parser[self.name])
    self.assertEqual(1, len(parser))

  def testOverWriteTemplate(self):
    """[Parser] AddTemplate overrides previously loaded template"""
    custom_raw = 'My very own [adj] template'
    custom_tmpl = templateparser.Template(custom_raw)
    parser = templateparser.Parser()
    parser.AddTemplate(self.name)
    # Create a new template in place of the existing one, and reload it.
    with file(self.name, 'w') as tmpl:
      tmpl.write(custom_raw)
      tmpl.flush()
    # Assert the template has not yet changed, load it, assert that is has.
    self.assertNotEqual(custom_tmpl, parser[self.name])
    parser.AddTemplate(self.name)
    self.assertEqual(custom_tmpl, parser[self.name])

  def testPreloadTemplates(self):
    """[Parser] Templates can be preloaded when instantiating the Parser"""
    parser = templateparser.Parser(templates=[self.name])
    self.assertEqual(1, len(parser))
    self.assertEqual(self.template, parser[self.name])

  def testParseVersusParseString(self):
    """[Parser] Parse and ParseString only differ in cached lookup"""
    parser = templateparser.Parser()
    result_parse = parser[self.name].Parse()
    result_parse_string = parser.ParseString(self.raw)
    self.assertEqual(result_parse, result_parse_string)


class ParserPerformance(unittest.TestCase):
  """Basic performance test of the Template's initialization and Parsing."""
  @staticmethod
  def testPerformance():
    """[Parser] Basic performance test for 2 template replacements"""
    for _template in range(100):
      template = 'This [obj:foo] is just a quick [bar]'
      tmpl = templateparser.Template(template)
      for _parse in xrange(100):
        tmpl.Parse(obj={'foo': 'template'}, bar='hack')


class TemplateTagBasic(unittest.TestCase):
  """Tests validity and parsing of simple tags."""
  def setUp(self):
    """Makes the Template class available on the instance."""
    self.tmpl = templateparser.Template

  def testTaglessTemplate(self):
    """[BasicTag] Templates without tags get returned verbatim as SafeString"""
    template = 'Template without any tags'
    parsed_template = self.tmpl(template).Parse()
    self.assertEqual(template, parsed_template)

  def testSafeString(self):
    """[BasicTag] Templates without tags get returned verbatim as SafeString"""
    template = 'Template without any tags'
    parsed_template = self.tmpl(template).Parse()
    self.assertTrue(isinstance(parsed_template, templateparser.SafeString))

  def testSingleTagTemplate(self):
    """[BasicTag] Templates with basic tags get returned proper"""
    template = 'Template with [single] tag'
    result = 'Template with just one tag'
    self.assertEqual(result, self.tmpl(template).Parse(single='just one'))

  def testCasedTag(self):
    """[BasicTag] Tag names are case-sensitive"""
    template = 'The parser has no trouble with [cAsE] [case].'
    result = 'The parser has no trouble with mixed [case].'
    self.assertEqual(result, self.tmpl(template).Parse(cAsE='mixed'))

  def testUnderscoredTag(self):
    """[BasicTag] Tag names may contain underscores"""
    template = 'The template may contain [under_scored] tags.'
    result = 'The template may contain underscored tags.'
    self.assertEqual(
        result, self.tmpl(template).Parse(under_scored='underscored'))

  def testMultiTagTemplate(self):
    """[BasicTag] Multiple instances of a tag will all be replaced"""
    template = '[adjective] [noun] are better than other [noun].'
    result = 'Beefy cows are better than other cows.'
    self.assertEqual(
        result, self.tmpl(template).Parse(noun='cows', adjective='Beefy'))

  def testEmptyOrWhitespace(self):
    """[BasicTag] Empty tags or tags containing whitespace aren't actual tags"""
    template = 'This [is a] broken [] template, really'
    self.assertEqual(template, self.tmpl(template).Parse(
        **{'is a': 'HORRIBLY', '': ', NASTY'}))

  def testBadCharacterTags(self):
    """[BasicTag] Tags containing bad characters are not considered tags"""
    bad_chars = """ :~!@#$%^&*()+-={}\|;':",./<>? """
    template = ''.join('[%s] [check]' % char for char in bad_chars)
    result = ''.join('[%s] ..' % char for char in bad_chars)
    replaces = dict((char, 'FAIL') for char in bad_chars)
    replaces['check'] = '..'
    self.assertEqual(result, self.tmpl(template).Parse(**replaces))

  def testUnreplacedTag(self):
    """[BasicTag] Template tags without replacement are returned verbatim"""
    template = 'Template with an [undefined] tag.'
    self.assertEqual(template, self.tmpl(template).Parse())

  def testBracketsInsideTag(self):
    """[BasicTag] Innermost bracket pair are the tag's delimiters"""
    template = 'Template tags may not contain [[spam][eggs]].'
    result = 'Template tags may not contain [opening or closing brackets].'
    self.assertEqual(result, self.tmpl(template).Parse(
        **{'[spam': 'EPIC', 'eggs]': 'FAIL', 'spam][eggs': 'EPIC FAIL',
           'spam': 'opening or ', 'eggs': 'closing brackets'}))


class TemplateTagIndexed(unittest.TestCase):
  """Tests the handling of complex tags (those with attributes/keys/indexes)."""
  def setUp(self):
    """Sets up a parser instance, as it never changes."""
    self.tmpl = templateparser.Template

  def testTemplateMappingKey(self):
    """[IndexedTag] Template tags can address mappings properly"""
    template = 'This uses a [dictionary:key].'
    result = 'This uses a spoon.'
    self.assertEqual(
        result, self.tmpl(template).Parse(dictionary={'key': 'spoon'}))

  def testTemplateIndexing(self):
    """[IndexedTag] Template tags can access indexed iterables"""
    template = 'Template that grabs the [obj:2] key from the given tuple/list.'
    result = 'Template that grabs the third key from the given tuple/list.'
    numbers = 'first', 'second', 'third'
    self.assertEqual(result, self.tmpl(template).Parse(obj=numbers))
    numbers = list(numbers)
    self.assertEqual(result, self.tmpl(template).Parse(obj=numbers))

  def testTemplateAttributes(self):
    """[IndexedTag] Template tags will do attribute lookups after key-lookups"""
    class Mapping(dict):
      """A subclass of a dictionary, so we can define attributes on it."""
      NAME = 'attribute'

    template = 'Template used [tag:NAME] lookup.'
    lookup_attr = 'Template used attribute lookup.'
    lookup_dict = 'Template used key (mapping) lookup.'

    mapp = Mapping()
    self.assertEqual(lookup_attr, self.tmpl(template).Parse(tag=mapp))
    mapp['NAME'] = 'key (mapping)'
    self.assertEqual(lookup_dict, self.tmpl(template).Parse(tag=mapp))

  def testTemplateMissingIndexes(self):
    """[IndexedTag] Tags with bad indexes will be returned verbatim"""
    class Object(object):
      """A simple object to store an attribute on."""
      NAME = 'Freeman'

    template = 'Hello [titles:1] [names:NAME], how is [names:other] [date:now]?'
    result = 'Hello [titles:1] Freeman, how is [names:other] [date:now]?'
    self.assertEqual(result, self.tmpl(template).Parse(
        titles=['Mr'], names=Object(), date={}))

  def testTemplateMultipleIndexing(self):
    """[IndexedTag] Template tags can contain multiple nested indexes"""
    template = 'Welcome to the [foo:bar:zoink].'
    result = 'Welcome to the World.'
    self.assertEqual(result, self.tmpl(template).Parse(
        foo={'bar': {'zoink': 'World'}}))


class TemplateTagFunctions(unittest.TestCase):
  """Tests the functions that are performed on replaced tags."""
  def setUp(self):
    """Sets up a parser instance, as it never changes."""
    self.parser = templateparser.Parser()

  def testBasicFunction(self):
    """[TagFunctions] Raw function does not affect output"""
    template = 'This function does [none|raw].'
    result = 'This function does "nothing".'
    self.assertEqual(result, self.parser.ParseString(
        template, none='"nothing"'))

  def testDefaultHtmlSafe(self):
    """[TagFunctions] The default function escapes HTML entities"""
    default = 'This function does [none].'
    escaped = 'This function does [none|html].'
    result = 'This function does &quot;nothing&quot;.'
    self.assertEqual(result, self.parser.ParseString(default, none='"nothing"'))
    self.assertEqual(result, self.parser.ParseString(escaped, none='"nothing"'))

  def testNoDefaultForSafeString(self):
    """[TagFunctions] The default function does not act upon SafeString parts"""
    first_template = 'Hello doctor [name]'
    second_template = '<assistant> [quote].'
    result = '<assistant> Hello doctor &quot;Who&quot;.'
    result_first = self.parser.ParseString(first_template, name='"Who"')
    result_second = self.parser.ParseString(second_template, quote=result_first)
    self.assertEqual(result, result_second)

  def testCustomFunction(self):
    """[TagFunctions] Custom functions can be added to the Parser"""
    self.parser.RegisterFunction('twice', lambda x: x + ' ' + x)
    template = 'The following will be stated [again|twice].'
    result = 'The following will be stated twice twice.'
    self.assertEqual(result, self.parser.ParseString(template, again='twice'))

  def testFunctionChaining(self):
    """[TagFunctions] Multiple functions can be chained after one another"""
    self.parser.RegisterFunction('len', len)
    self.parser.RegisterFunction('count', lambda x: '%s characters' % x)
    template = 'A replacement processed by two functions: [spam|len|count].'
    result = 'A replacement processed by two functions: 8 characters.'
    self.assertEqual(result, self.parser.ParseString(template, spam='ham&eggs'))

  def testFunctionSeparation(self):
    """[TagFunctions] Tag functions are only called when requested by tags"""
    fragments_received = []
    def CountAndReturn(fragment):
      """Returns the given fragment after adding it to a counter list."""
      fragments_received.append(fragment)
      return fragment

    self.parser.RegisterFunction('count', CountAndReturn)
    template = 'Count only has [num|count] call, or it is [noun|raw].'
    result = 'Count only has one call, or it is broken.'
    self.assertEqual(result, self.parser.ParseString(
        template, num='one', noun='broken'))
    self.assertEqual(1, len(fragments_received))


class TemplateUnicodeSupport(unittest.TestCase):
  """TemplateParser handles Unicode gracefully."""
  def setUp(self):
    """Sets up a parser instance, as it never changes."""
    self.parser = templateparser.Parser()

  def testUnicodeReplacements(self):
    """[Unicode] Unicode in tag replacements is converted to utf8"""
    template = 'Underdark Web framework, also known as [name].'
    result = u'Underdark Web framework, also known as \xb5Web.'.encode('utf8')
    name = u'\xb5Web'
    self.assertEqual(result, self.parser.ParseString(template, name=name))

  def testUnicodeTagFunction(self):
    """[Unicode] Template functions returning unicode are converted to utf8"""
    function_result = u'No more \N{BLACK HEART SUIT}'
    def StaticReturn(_fragment):
      """Returns a static string, for any input fragment."""
      return function_result

    self.parser.RegisterFunction('nolove', StaticReturn)
    template = '[love|nolove]'
    result = function_result.encode('utf8')
    self.assertEqual(result, self.parser.ParseString(template, love='love'))

  def testUnicodeTemplate(self):
    """[Unicode] Templates may contain utf8"""
    template = u'We \u2665 \xb5Web!'.encode('utf8')
    self.assertEqual(template, self.parser.ParseString(template))


class TemplateInlining(unittest.TestCase):
  """TemplateParser properly handles the include statement."""
  def setUp(self):
    """Sets up a testbed."""
    self.parser = templateparser.Parser()
    self.tmpl = templateparser.Template

  def testInlineExisting(self):
    """{{ inline }} Parser will inline an already existing template reference"""
    self.parser['template'] = self.tmpl('This is a subtemplate by [name].')
    template = '{{ inline template }}'
    result = 'This is a subtemplate by Elmer.'
    self.assertEqual(result, self.parser.ParseString(template, name='Elmer'))

  def testInlineFile(self):
    """{{ inline }} Parser will load an inlined template from file if needed"""
    with file('tmp_template', 'w') as inline_file:
      inline_file.write('This is a subtemplate by [name].')
      inline_file.flush()
    try:
      template = '{{ inline tmp_template }}'
      result = 'This is a subtemplate by Elmer.'
      self.assertEqual(result, self.parser.ParseString(template, name='Elmer'))
    finally:
      os.unlink('tmp_template')


class TemplateConditionals(unittest.TestCase):
  """TemplateParser properly handles if/elif/else statements."""
  def setUp(self):
    """Sets up a testbed."""
    self.parser = templateparser.Parser()

  def testBasicConditional(self):
    """{{ if }} Basic boolean check works for relevant data types"""
    template = '{{ if [variable] }} foo {{ endif }}'
    # Boolean True inputs should return a SafeString object stating 'foo'.
    self.assertTrue(self.parser.ParseString(template, variable=True))
    self.assertTrue(self.parser.ParseString(template, variable='truth'))
    self.assertTrue(self.parser.ParseString(template, variable=12))
    self.assertTrue(self.parser.ParseString(template, variable=[1, 2]))
    # Boolean False inputs should yield an empty SafeString object.
    self.assertFalse(self.parser.ParseString(template, variable=None))
    self.assertFalse(self.parser.ParseString(template, variable=0))
    self.assertFalse(self.parser.ParseString(template, variable=''))

  def testCompareTag(self):
    """{{ if }} Basic tag value comparison"""
    template = '{{ if [variable] == 5 }} foo {{ endif }}'
    self.assertFalse(self.parser.ParseString(template, variable=0))
    self.assertFalse(self.parser.ParseString(template, variable=12))
    self.assertTrue(self.parser.ParseString(template, variable=5))

  def testTagIsInstance(self):
    """{{ if }} Basic tag value comparison"""
    template = '{{ if isinstance([variable], int) }} foo {{ endif }}'
    self.assertFalse(self.parser.ParseString(template, variable=[1]))
    self.assertFalse(self.parser.ParseString(template, variable='number'))
    self.assertTrue(self.parser.ParseString(template, variable=5))

  def testDefaultElse(self):
    """{{ if }} Else block will be parsed when `if` fails"""
    template = '{{ if [var] }}foo {{ else }}bar {{ endif }}'
    self.assertEqual('foo', self.parser.ParseString(template, var=True))
    self.assertEqual('bar', self.parser.ParseString(template, var=False))

  def testElif(self):
    """{{ if }} Elif blocks will be parsed until one matches"""
    template = """
        {{ if [var] == 1 }}a
        {{ elif [var] == 2 }}b
        {{ elif [var] == 3 }}c
        {{ elif [var] == 4 }}d
        {{ endif }}"""
    self.assertEqual('a', self.parser.ParseString(template, var=1))
    self.assertEqual('b', self.parser.ParseString(template, var=2))
    self.assertEqual('c', self.parser.ParseString(template, var=3))
    self.assertEqual('d', self.parser.ParseString(template, var=4))
    self.assertFalse(self.parser.ParseString(template, var=5))

  def testIfElifElse(self):
    """{{ if }} Full if/elif/else branch is functional all work"""
    template = """
        {{ if [var] == "a" }}1
        {{ elif [var] == "b"}}2
        {{ else }}3 {{ endif }}"""
    self.assertEqual('1', self.parser.ParseString(template, var='a'))
    self.assertEqual('2', self.parser.ParseString(template, var='b'))
    self.assertEqual('3', self.parser.ParseString(template, var='c'))

  def testSyntaxErrorNoEndif(self):
    """{{ if }} Conditional without {{ endif }} raises TemplateSyntaxError"""
    template = '{{ if [var] }} foo'
    self.assertRaises(
        templateparser.TemplateSyntaxError, self.parser.ParseString, template)

  def testSyntaxErrorElifAfterElse(self):
    """{{ if }} An `elif` clause following `else` raises TemplateSyntaxError"""
    template = '{{ if [var] }} {{ else }} {{ elif [var] }} {{ endif }}'
    self.assertRaises(
        templateparser.TemplateSyntaxError, self.parser.ParseString, template)

  def testSyntaxErrorDoubleElse(self):
    """{{ if }} Starting a second `else` clause raises TemplateSyntaxError"""
    template = '{{ if [var] }} {{ else }} {{ else }} {{ endif }}'
    self.assertRaises(
        templateparser.TemplateSyntaxError, self.parser.ParseString, template)

  def testSyntaxErrorClauseWithoutIf(self):
    """{{ if }} elif / else / endif without `if` raises TemplateSyntaxError"""
    template = '{{ elif }}'
    self.assertRaises(
        templateparser.TemplateSyntaxError, self.parser.ParseString, template)
    template = '{{ else }}'
    self.assertRaises(
        templateparser.TemplateSyntaxError, self.parser.ParseString, template)
    template = '{{ endif }}'
    self.assertRaises(
        templateparser.TemplateSyntaxError, self.parser.ParseString, template)

  def testVariableMustBeTag(self):
    """{{ if }} Clauses must reference variables using a tag, not a name"""
    good_template = '{{ if [var] }} x {{ else }} x {{ endif }}'
    self.assertTrue(self.parser.ParseString(good_template, var='foo'))
    bad_template = '{{ if var }} x {{ else }} x {{ endif }}'
    self.assertRaises(templateparser.TemplateNameError,
                      self.parser.ParseString,
                      bad_template, var='foo')

  def testLazyEvaluation(self):
    """{{ if }} Variables are retrieved in lazy fashion, not before needed"""
    # Tags are looked up lazily
    template = '{{ if [present] or [absent] }}~ {{ endif }}'
    self.assertEqual('~', self.parser.ParseString(template, present=True))

    # Indices are looked up lazily
    template = '{{ if [var:present] or [var:absent] }}~ {{ endif }}'
    self.assertEqual('~', self.parser.ParseString(template, var={'present': 1}))


class TemplateLoops(unittest.TestCase):
  """TemplateParser properly handles for-loops."""
  def setUp(self):
    """Sets up a testbed."""
    self.parser = templateparser.Parser()
    self.tmpl = templateparser.Template

  def testLoopCount(self):
    """{{ for }} Parser will loop once for each item in the for loop"""
    template = '{{ for num in [values] }}x{{ endfor }}'
    result = 'xxxxx'
    self.assertEqual(result, self.parser.ParseString(template, values=range(5)))

  def testLoopReplaceBasic(self):
    """{{ for }} The loop variable is available via tagname"""
    template = '{{ for num in [values] }}[num],{{ endfor }}'
    result = '0,1,2,3,4,'
    self.assertEqual(result, self.parser.ParseString(template, values=range(5)))

  def testLoopReplaceScope(self):
    """{{ for }} The loop variable overwrites similar names from outer scope"""
    template = '[num], {{ for num in [numbers] }}[num], {{ endfor }}[num]'
    result = 'OUTER,0,1,2,3,4,OUTER'
    self.assertEqual(result, self.parser.ParseString(
        template, numbers=range(5), num='OUTER'))

  def testLoopOverIndexedTag(self):
    """{{ for }} Loops can be performed over indexed tags"""
    template = '{{ for num in [numbers:1] }}x{{ endfor }}'
    result = 'xxxxx'
    self.assertEqual(result, self.parser.ParseString(
      template, numbers=[range(10), range(5), range(10)]))

  def testLoopVariableIndex(self):
    """{{ for }} Loops variable tags support indexing and functions"""
    template = '{{ for bundle in [bundles]}}[bundle:1:name|upper], {{ endfor }}'
    bundles = [('1', {'name': 'Spam'}), ('2', {'name': 'Eggs'})]
    result = 'SPAM,EGGS,'
    self.parser.RegisterFunction('upper', str.upper)
    self.assertEqual(result, self.parser.ParseString(template, bundles=bundles))


class TemplateNestedScopes(unittest.TestCase):
  """Test cases for nested function scopes."""
  def setUp(self):
    """Sets up a testbed."""
    self.parser = templateparser.Parser()
    self.tmpl = templateparser.Template

  def testLoopWithInline(self):
    """{{ nested }} Loops can contain an {{ inline }} section"""
    inline = '<li>Hello [name]</li>'
    self.parser['name'] = self.tmpl(inline)
    names = 'John', 'Eric'
    template = '{{ for name in [names] }}{{ inline name }}{{ endfor }}'
    result = '<li>Hello John</li><li>Hello Eric</li>'
    self.assertEqual(result, self.parser.ParseString(template, names=names))

  def testLoopWithInlineLoop(self):
    """{{ nested }} Loops can contain {{ inline }} loops"""
    inline = '{{ for char in [name] }}[char].{{ endfor }}'
    self.parser['name'] = self.tmpl(inline)
    names = 'John', 'Eric'
    template = '{{ for name in [names] }}<li>{{ inline name }}</li>{{ endfor }}'
    result = '<li>J.o.h.n.</li><li>E.r.i.c.</li>'
    self.assertEqual(result, self.parser.ParseString(template, names=names))

  def testInlineLoopsInConditional(self):
    """{{ nested }} Inlined loop in a conditional without problems"""
    self.parser['loop'] = self.tmpl('{{ for i in [loops] }}[i]{{ endfor }}')
    self.parser['once'] = self.tmpl('value: [value]')
    tmpl = '{{ if [x] }}{{ inline loop }}{{ else }}{{ inline once }}{{ endif }}'
    self.assertEqual('12345', self.parser.ParseString(
        tmpl, loops=range(1, 6), x=True))
    self.assertEqual('value: foo', self.parser.ParseString(
        tmpl, value='foo', x=False))


if __name__ == '__main__':
  unittest.main(testRunner=unittest.TextTestRunner(verbosity=2))
