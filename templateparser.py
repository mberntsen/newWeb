#!/usr/bin/python2.5
"""A simple implementation of a template parser

Classes:
  Parser: Parses a template by replacing tags with their values.

Error classes:
  Error: Default error class for templateparser
  TemplateReadError: Template file could not be read or found.
"""
__author__ = 'Elmer de Looff <elmer@underdark.nl'
__version__ = '1.1'

# Standard modules
import os
import re
import urllib


class Error(Exception):
  """Superclass used for inheritance and external exception handling."""


class TemplateKeyError(Error):
  """There is no replacement with the requested key."""


class TemplateSyntaxError(Error):
  """The template contains illegal syntax."""


class TemplateReadError(Error, IOError):
  """Template file could not be read or found."""


class Parser(dict):
  """A template parser that loads and caches templates and parses them by name.

  After initializing the parser with a search path for templates, new templates
  can be explicitly added by using the `AddTemplate` method, or by using either
  key-based access or using the `Parse` method. These templates are loaded from
  file, though inserted into the Parser cache are Template objects. These are
  constructed into their separate components for faster parsing.

  The `Parse` method takes a template name and any number of keyword arguments.
  The template name is used to fetch the desired Template object from the
  Parser cache (or to load it automatically). This Template object is then
  parsed using the provided keyword arguments.

  Alternatively, there is the `ParseString` method, which works in much the same
  way as the `Parse` method, but the first argument here is a raw template
  string instead.

  Beyond parsing, the parser grants easy access to the TAG_FUNCTIONS dictionary,
  providing the `RegisterFunction` method to add or replace functions in this
  module constant.
  """
  def __init__(self, path='.', templates=()):
    """Initializes a Parser instance.

    This sets up the template directory and preloads any templates given.

    Arguments:
      % path: str ~~ '.'
        Search path for loading templates using AddTemplate().
      % templates: iter of str ~~ None
        Names of templates to preload.
    """
    super(Parser, self).__init__()
    self.template_dir = path
    for template in templates:
      self.AddTemplate(template)

  def __getitem__(self, template):
    """Retrieves a stored template by name.

    If the template is not already present, it will be loaded from disk.
    The template name will be searched on the defined `template_dir`, if it's
    not found a `TemplateReadError` is raised.

    Arguments:
      @ template: str
        Template name, or the relative path to find it on.

    Raises:
      TemplateReadError: Template name doesn't exist and cannot be loaded.

    Returns:
      Template: A template object, created from a previously loaded file.
    """
    if template not in self:
      self.AddTemplate(template)
    return super(Parser, self).__getitem__(template)

  def AddTemplate(self, template):
    """Reads the given `template` file and adds it to the cache.

    The `template` given is a path that is then resolved against the configured
    `template_dir` instance attribute. The resulting filename is used to load
    a Template object, which is then stored in the Parser cache under the given
    `template` name.

    Raises:
      TemplateReadError: When the template file cannot be read
    """
    try:
      template_path = os.path.join(self.template_dir, template)
      self[template] = Template.FromFile(template_path, parser=self)
    except IOError:
      raise TemplateReadError('Could not load template %r' % template_path)

  def Parse(self, template, **replacements):
    """Returns the referenced template with its tags replaced by **replacements.

    This method automatically loads the referenced template if it doesn't exist.
    The template is loaded from the `template_dir` defined on the instance.

    Arguments:
      @ template: str
        Template name, or the relative path to find it on.
      @ **replacements: dict
        Dictionary of replacement objects. Tags are looked up in here.

    Returns:
      str: The template with relevant tags replaced by the replacement dict.
    """
    return self[template].Parse(**replacements)

  def ParseString(self, template, **replacements):
    """Returns the given `template` with its tags replaced by **replacements.

    Arguments:
      @ template: str
        The literal template string, where tags are replaced. This is not stored
        in the internal template dictionary, nor is it requested therein.
      @ replacements: dict
        Dictionary of replacement objects. Tags are looked up in here.


    Returns:
      str: template with replaced tags.
    """
    return Template(template, parser=self).Parse(**replacements)

  @staticmethod
  def RegisterFunction(name, function):
    """Registers a templating `function`, allowing use in templates by `name`.

    Arguments:
      @ name: str
        The name of the template function. This can be used behind a pipe ( | )
      @ function: function
        The function that should be used. Ideally this returns a string.
    """
    TAG_FUNCTIONS[name] = function

  TemplateReadError = TemplateReadError

class SafeString(str):
  """A template string, which has had all its processing done already."""


class Template(list):
  """Contained for template parts, allowing for rich content construction."""
  # Tags are delimited by square brackets, and must contain only the following:
  # - Alphanumeric characters (a-zA-Z0-9)
  # - underscores, pipes or colons (_|:)
  # Whitespace or other illegal characters inside tags will make them literals.
  FUNCTION = re.compile(r'\{\{\s*(.*?)\s*\}\}')
  TAG = re.compile(r'\[([\w:|]+)\]')

  def __init__(self, raw_template, parser=None):
    """Initializes a Template

    The optional parser is used to load templates using AddFile() where
    available. Adding a parser will allow Template to benefit from the caching
    performed by Parser. Without this, AddFile will still work but not benefit
    from this caching.

    Arguments:
      @ raw_template: str
        A string to begin a template with. This is parsed and used to build the
        initial raw template from.
      % parser: Parser ~~ None
        The Parser instance to use for speeding up AddFile through caching.
    """
    super(Template, self).__init__()
    self.parser = parser
    self.scopes = [self]
    self.AddString(raw_template)

  def __eq__(self, other):
    """Returns the equality to another Template.

    Two templates are equal if they are of the same type, and have the same
    content for their unparsed template; or string representation.
    """
    return isinstance(other, type(self)) and str(other) == str(self)

  def __repr__(self):
    return '%s(%s)' % (type(self).__name__, list(self))

  def __str__(self):
    return ''.join(map(str, self))

  @classmethod
  def FromFile(cls, template_path, parser=None):
    """Returns a Template after reading the given template file.

    Arguments:
      @ template_path: str
        The path and filename of the file to read and create a template from.
      % parser: Parser ~~ None
        The parser object to pass along to the new Template.
    """
    try:
      with file(template_path) as template:
        return cls(template.read(), parser=parser)
    except IOError:
      raise TemplateReadError('Cannot open: %r' % template_path)

  def AddFile(self, name):
    """Extends the Template by reading template data from a file.

    If a Parser instance is present on the Template, the file is loaded through
    this parser, making use of its caching capabilities. If it is not present,
    an attempt is made to load the file from within the Template itself.

    Raises:
      TemplateReadError: Whenever the template file could not be read.
    """
    if self.parser is not None:
      return self._AddPart(self.parser[name])
    return self.FromFile(name)

  def AddString(self, raw_template):
    """Extends the Template by adding a raw template string.

    The given template is parsed and added to the existing template.

    Raises:
      TemplateSyntaxError: Unbalanced number of scopes in added template.
    """
    scope_depth = len(self.scopes)
    nodes = self.FUNCTION.split(raw_template)
    for index, node in enumerate(nodes):
      if index % 2:
        self._ExtendFunction(node)
      else:
        self._ExtendText(node)
    if len(self.scopes) != scope_depth:
      scope_diff = len(self.scopes) - scope_depth
      if scope_diff < 0:
        raise TemplateSyntaxError('Closed %d scopes too many' % abs(scope_diff))
      raise TemplateSyntaxError('Template left %d open scopes.' % scope_diff)

  def Parse(self, **kwds):
    """Returns the parsed template as SafeString.

    The template is parsed by parsing each of its members and combining that.
    """
    return SafeString(''.join(tag.Parse(**kwds) for tag in self))

  def _ExtendFunction(self, node):
    """Processes a function node and adds its results to the Template.

    For loops, a new scope level is opened by adding the TemplateLoop to the
    `scopes` instance attribute. Upon finding the end of a loop, the topmost
    scope is removed, provided it is a TemplateLoop scope. If it is not,
    TemplateSyntaxError is raised.

    Raises:
      TemplateSyntaxError: Unexpected / unknown command or otherwise bad syntax.
    """
    data = node.split()
    name = data.pop(0)
    if name == 'inline':
      self.AddFile(data[0])
    elif name == 'for':
      alias, _in, tag = data
      if not Template.TAG.match(tag):
        raise TemplateSyntaxError('Tag %r in {{ for }} loop is not valid' % tag)
      loop = TemplateLoop(tag, alias)
      self._AddPart(loop)
      self.scopes.append(loop)
    elif name == 'endfor':
      if isinstance(self.scopes[-1], TemplateLoop):
        self.scopes.pop()
      else:
        raise TemplateSyntaxError('Unexpected {{ endfor }}')
    else:
      raise TemplateSyntaxError('Unknown template function %r' % name)

  def _ExtendText(self, node):
    """Processes a text node and adds its tags and texts to the Template."""
    nodes = self.TAG.split(node)
    for index, node in enumerate(nodes):
      if index % 2:
        self._AddPart(TemplateTag.FromString(node))
      elif node:
        self._AddPart(TemplateText(node))

  def _AddPart(self, item):
    """Adds a template part to the current open scope."""
    self.scopes[-1].append(item)


class TemplateLoop(list):
  """Template loops are used to repeat a portion of template multiple times.

  Upon parsing, the loop tag is retrieved, and for each of its members, the
  items in the loop are parsed. The loop variable is made available as the given
  alias, which itself can be referenced as a tag in the loop body.
  """
  def __init__(self, tag, alias):
    """Initializes a TemplateLoop instance.

    Arguments:
      @ tag: str
        The tag to retrieve the iterable from.
      @ alias: str
        The alias under which the loop variable should be made available.
    """
    super(TemplateLoop, self).__init__()
    self.tag = TemplateTag.FromString(tag)
    self.alias = alias

  def __repr__(self):
    return '%s(%s)' % (type(self).__name__, list(self))

  def __str__(self):
    return '{{ for %s in %s }}%s{{ endfor }}' % (
        self.alias, self.tag, ''.join(map(str, self)))

  def Parse(self, **kwds):
    """Returns the TemplateLoop parsed as string.

    Firstly, the value for the loop tag is retrieved. For each item in this
    iterable, all members of the TemplateLoop body will be parsed, with the
    item from the iterable added to the replacements dict as `self.alias`.
    """
    output = []
    replacements = kwds.copy()
    for alias in self.tag.GetValue(**kwds):
      replacements[self.alias] = alias
      output.append(''.join(tag.Parse(**replacements) for tag in self))
    return ''.join(output)


class TemplateTag(object):
  """Template tags are used for dynamic placeholders in templates.

  Their final value is determined during parsing. For more explanation on this,
  refer to the documentation for Parse().
  """
  INDEX_PREFIX = ':'
  FUNCT_PREFIX = '|'
  TAG_DELIMITERS = '[]'

  def __init__(self, name, indices=(), functions=()):
    """Initializes a TemplateTag instant.

    Arguments:
      @ name: str
        The name of the tag, to retrieve it from the replacements dictionary.
      % indices: iterable ~~ None
        Indices that should be applied to arrive at the proper tag value.
      % functions: iterable ~~ None
        Names of template functions that should be applied to the value.
    """
    self.name = name
    self.indices = indices
    self.functions = functions

  def __repr__(self):
    return '%s(%r)' % (type(self).__name__, str(self))

  def __str__(self):
    return '[%s%s%s]' % (
        self.name,
        ''.join(self.INDEX_PREFIX + index for index in self.indices),
        ''.join(self.FUNCT_PREFIX + func for func in self.functions))

  @classmethod
  def FromString(cls, tag):
    """Returns a TemplateTag object which is parsed from the given string.

    A tag's formatting restrictions are as follows:
      * The whole tag is delimited by square brackets: []
      * Indices are separated by colons, :, multiple are allowed
      * Functions are prefixed by pipes, |, multiple are allowed
      * In addition to the characters stated above, tags may contain only
        alphanumeric values, underscores and dashes. Spaces are _not_ allowed.
    """
    tag_and_funcs = tag.strip(cls.TAG_DELIMITERS).split(cls.FUNCT_PREFIX)
    name_and_indices = tag_and_funcs[0].split(cls.INDEX_PREFIX)
    return cls(name_and_indices[0], name_and_indices[1:], tag_and_funcs[1:])

  def GetValue(self, **kwds):
    """Returns the value for the tag, after reducing indices.

    For a tag with indices, these are looked up one after the other, each index
    being that of the next step. [tag:0:0] for with a keyword tag=[['foo']]
    would given 'foo' as the value for the tag.
    """
    try:
      value = kwds[self.name]
      for index in self.indices:
        value = self._GetIndex(value, index)
      return value
    except KeyError:
      raise TemplateKeyError('No replacement with name %r' % self.name)

  def Parse(self, **kwds):
    """Returns the parsed string of the tag, using given replacements.

    Firstly, the tag's name is retrieved from the given replacements dictionary.

    After that, for a tag with indices, these are looked up one after the other,
    each index being that of the next step. `[tag:0:0]` with a replacements
    dictionary {tag=[['foo']]} will reduce to 'foo' as the value for the tag.

    After reducing indexes, functiones are applied. As before, functions are
    applied one after the other. The second function works on the result of the
    first. If no functions are defined for a tag, the default tag function
    will be applied. SafeString objects are exempt from this default function;
    They will only be acted upon by functions as specified in the tag.

    All tag functions are derived from the module constant TAG_FUNCTIONS, and
    are looked up when requested. This means that if a function is changed after
    the template has been created, the new function will be used instead.
    """
    try:
      value = self.GetValue(**kwds)
    except TemplateKeyError:
      # On any failure to get the given index, return the unmodified tag.
      return str(self)
    # Process functions, or apply default if value is not SafeString
    if self.functions:
      for func in self.functions:
        value = TAG_FUNCTIONS[func](value)
    else:
      if not isinstance(value, SafeString):
        value = TAG_FUNCTIONS['default'](value)

    if isinstance(value, unicode):
      return value.encode('utf8')
    return value

  @staticmethod
  def _GetIndex(haystack, needle):
    """Returns the `needle` from the `haystack` by index, key or attribute name.

    Arguments:
      @ haystack: obj
        The searched object; iterable, mapping or any kind of object.
      @ needle: str
        The index, key or attribute name to find on the haystack.

    Raises:
      TemplateKeyError: One or more of the given needles don't exist.

    Returns:
      obj: the object existing on `needle` in `haystack`.
      """
    try:
      if needle.isdigit():
        try:
          # `needle` is a number; likely an index or a numeric dict-key.
          return haystack[int(needle)]
        except KeyError:
          # `haystack` should be a dict; numeric attributes are invalid syntax.
          return haystack[needle]
      try:
        # `needle` is a string; either a dict-key, or an attribute name.
        return haystack[needle]
      except (KeyError, TypeError):
        # KeyError, `haystack` has no key `needle` but may have matching attr.
        # TypeError: `haystack` is no mapping but may have a matching attr.
        return getattr(haystack, needle)
    except (AttributeError, LookupError):
      raise TemplateKeyError('Item has no index, key or attribute %r.' % needle)


class TemplateText(str):
  """A raw piece of template text, upon which no replacements will be done."""
  def __repr__(self):
    """Returns the object representation of the TemplateText."""
    return '%s(%r)' % (type(self).__name__, str(self))

  def Parse(self, **_kwds):
    """Returns the string value of the TemplateText."""
    return str(self)


def HtmlEscape(text):
  """Escapes the 5 characters deemed by XML to be unsafe if left unescaped.

  The relevant defined set consists of the following characters: &'"<>

  Takes:
    @ html: str
      The html string with html character entities.

  Returns:
    str: the input, after turning entites back into raw characters.
  """
  if not isinstance(text, basestring):
    text = unicode(text)
  html = text.replace('&', '&amp;')
  html = html.replace('"', '&quot;')
  html = html.replace("'", '&#39;')  # &apos; is valid, but poorly supported.
  html = html.replace('>', '&gt;')
  return html.replace('<', '&lt;')


TAG_FUNCTIONS = {
    'default': HtmlEscape,
    'html': HtmlEscape,
    'raw': lambda x: x,
    'url': urllib.quote_plus}
