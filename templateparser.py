#!/usr/bin/python2.5
"""A simple implementation of a template parser

Classes:
  Parser: Parses a template by replacing tags with their values.

Error classes:
  Error: Default error class for templateparser
  TemplateReadError: Template file could not be read or found.
"""
__author__ = 'Elmer de Looff <elmer@underdark.nl'
__version__ = '1.0'

# Standard modules
import os
import re
import urllib

# Tags are delimited by square brackets, and must contain only the following:
# - Alphanumeric characters (a-zA-Z0-9)
# - underscores, pipes or colons (_|:)
# Whitespace or other illegal characters trigger literal processing of brackets.
TEMPLATE_FUNCTION = re.compile(r'\{\{\s*(.*?)\s*\}\}')
TEMPLATE_TAG = re.compile(r'\[([\w:|]+)\]')


class Error(Exception):
  """Superclass used for inheritance and external exception handling."""


class TemplateKeyError(Error):
  """There is no replacement with the requested key."""


class TemplateSyntaxError(Error):
  """The template contains illegal syntax."""


class TemplateReadError(Error, IOError):
  """Template file could not be read or found."""


class Parser(dict):
  """Template parser \o/

  Methods:
    __init__: Initializes the template parser.
    Parse: Parses a template by replacing tags with their values.

  Members:
    path:      str - Path to the templates, absolute or relative.
    templates: dict - Names of the templates with their template data.
  """
  def __init__(self, path='.', templates=()):
    """Initializes the template parser.

    This sets up the template directory and preloads templates if required.

    Arguments:
      path:      str - Template directory path.
      templates: list of str - Names of templates to preload. Default None.
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

    Returns:
      Template: A template object, created from a previously loaded file.

    Raises:
      TemplateReadError: Template name doesn't exist and cannot be loaded.
    """
    if template not in self:
      self.AddTemplate(template)
    return super(Parser, self).__getitem__(template)

  def AddTemplate(self, template):
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
      str - The template with relevant tags replaced by the replacement dict.
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
      str, template with replaced tags.
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
  def __init__(self, raw_template, parser=None):
    super(Template, self).__init__()
    self.parser = parser
    self.scopes = [self]
    self.AddString(raw_template)

  def __repr__(self):
    return '%s(%s)' % (type(self).__name__, list(self))

  def __str__(self):
    return ''.join(map(str, self))

  @classmethod
  def FromFile(cls, template_path, parser=None):
    try:
      with file(template_path) as template:
        return cls(template.read(), parser=parser)
    except IOError:
      raise TemplateReadError('Cannot open: %r' % template_path)

  def AddString(self, raw_template):
    scope_depth = len(self.scopes)
    nodes = TEMPLATE_FUNCTION.split(raw_template)
    for index, node in enumerate(nodes):
      if index % 2:
        self._ExtendFunction(node)
      else:
        self._ExtendText(node)
    if len(self.scopes) != scope_depth:
      raise TemplateSyntaxError('Incorrect number of open scopes.')

  def AddTemplate(self, name):
    if self.parser is not None:
      return self._AddPart(self.parser[name])
    raise TemplateReadError('Cannot add template without a parser present.')

  def Parse(self, **kwds):
    output = []
    for tag in self:
      output.append(tag.Parse(**kwds))
    return SafeString(''.join(output))

  def _ExtendFunction(self, node):
    data = node.split()
    name = data.pop(0)
    if name == 'inline':
      self.AddTemplate(data[0])
    elif name == 'for':
      alias, _in, tag = data
      loop = TemplateLoop(self, tag, alias)
      self._AddPart(loop)
      self.scopes.append(loop)
    elif name == 'endfor':
      if isinstance(self.scopes[-1], TemplateLoop):
        self.scopes.pop()
      else:
        raise TemplateSyntaxError('Unexpected {{ endfor }}')
    else:
      raise TemplateSyntaxError('Unexpected command %r' % name)

  def _ExtendText(self, node):
    nodes = TEMPLATE_TAG.split(node)
    for index, node in enumerate(nodes):
      if index % 2:
        self._AddPart(TemplateTag.FromString(node))
      elif node:
        self._AddPart(TemplateText(node))

  def _AddPart(self, item):
    self.scopes[-1].append(item)


class TemplateLoop(list):
  def __init__(self, template, tag, alias):
    super(TemplateLoop, self).__init__()
    self.template = template
    self.tag = TemplateTag.FromString(tag)
    self.alias = alias

  def __repr__(self):
    return '%s(%s)' % (type(self).__name__, list(self))

  def __str__(self):
    return '{{ for %s in %s }} %s {{ endfor }}' % (
        self.alias, self.tag, ''.join(map(str, self)))

  def Parse(self, **kwds):
    output = []
    replacements = kwds.copy()
    for alias in self.tag.Get(**kwds):
      replacements[self.alias] = alias
      output.append(''.join(tag.Parse(**replacements) for tag in self))
    return ''.join(output)


class TemplateTag(object):
  def __init__(self, name, indices=(), functions=()):
    self.name = name
    self.indices = indices
    self.functions = functions

  def __repr__(self):
    return '%s(%r)' % (type(self).__name__, str(self))

  def __str__(self):
    return '[%s%s%s]' % (self.name,
                         ''.join(':%s' % index for index in self.indices),
                         ''.join('|%s' % func for func in self.functions))

  @classmethod
  def FromString(cls, tag):
    tag_and_funcs = tag.strip('[]').split('|')
    name_and_indices = tag_and_funcs[0].split(':')
    return cls(name_and_indices[0], name_and_indices[1:], tag_and_funcs[1:])

  def Get(self, **kwds):
    try:
      return kwds[self.name]
    except KeyError:
      raise TemplateKeyError('No replacement with name %r' % self.name)

  def Parse(self, **kwds):
    try:
      value = kwds[self.name]
      for index in self.indices:
        value = self._GetIndex(value, index)
    except (AttributeError, LookupError):
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
        The replacement object, iterable, mapping or any kind of object.
      @ needle: str
        The index, key or attribute name to find on the replacement.

    Raises:
      IndexError: the int()'ed `index` does not exist on the `replacement`.
      AttributeError: resulting error if the `index` does not exist in any form.

    Returns:
      str, the string contained on the `index` of the replacement.
      """
    if needle.isdigit():
      try:
        # `needle` is a number so either an index, or a numeric dict-key
        return haystack[int(needle)]
      except KeyError:
        # `haystack` is a dictionary, or a numeric key is illegal
        return haystack[needle]
    try:
      # `needle` is a string, so either a dict-key, or an attribute name.
      return haystack[needle]
    except (KeyError, TypeError):
      # KeyError, `needle` is not a key, but may still be an attribute.
      # TypeError: `haystack` is no dict, but may have attributes nonetheless.
      return getattr(haystack, needle)


class TemplateText(object):
  def __init__(self, value):
    self.value = value

  def __repr__(self):
    return '%s(%r)' % (type(self).__name__, str(self))

  def __str__(self):
    return self.value

  def Parse(self, **_kwds):
    return self.value


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
  html = html.replace('\'', '&#39;')  # &apos; is valid, but poorly supported.
  html = html.replace('>', '&gt;')
  return html.replace('<', '&lt;')


TAG_FUNCTIONS = {
    'default': HtmlEscape,
    'html': HtmlEscape,
    'raw': lambda x: x,
    'url': urllib.quote_plus}
