#!/usr/bin/python2.5
"""A simple implementation of a template parser

Classes:
  Parser: Parses a template by replacing tags with their values.

Error classes:
  Error: Default error class for templateparser
  TemplateReadError: Template file could not be read or found.
"""
__author__ = 'Jan Klopper & Elmer de Looff'
__version__ = '0.5'

# Standard modules
import itertools
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
    super(Parser, self).__init__(templates)
    self.template_dir = path

  def __getitem__(self, template):
    """Retrieves a stored template by name.

    If the template is not already present, it will be loaded from disk.
    The template name will be searched on the defined `template_dir`, if it's
    not found a `TemplateReadError` is raised.

    Arguments:
      @ template: str
        Template name, or the relative path to find it on.

    Returns:
      2-tuple: static template parts, template tags.

    Raises:
      TemplateReadError: Template name doesn't exist and cannot be loaded.
    """
    if template not in self:
      template_path = os.path.join(self.template_dir, template)
      self[template] = Template.FromFile(self, template_path)
    return super(Parser, self).__getitem__(template)

#  def __setitem__(self, name, template):
#    """Stores the `template` using the given `name` after pre-parsing."""
#    super(Parser, self).__setitem__(name, self._PreParse(template))

  def _Parse(self, template, replacements):
    """Replaced template-tags, and interleaves them with static template parts.

    Arguments:
      @ template: 2-tuple
        Text parts and tags from the template.
      @ replacements: dict
        Dictionary of replacement objects. Tags are looked up in here.

    Returns: str, the template with replaced tags.
    """
    texts, tags = template
    return SafeString(''.join(x.next() for x in itertools.cycle(
        (iter(texts), self._TagReplace(tags, replacements)))))

  def _PreParse(self, template):
    template = ''.join(self._ProcessFunctions(template))
    return self._SplitTags(template)

  def _ProcessFunctions(self, template):
    nodes = TEMPLATE_FUNCTION.split(template)
    for index, node in enumerate(nodes):
      if bool(index % 2):
        # node is a function
        name, data = node.split(None, 1)
        if name == 'inline':
          with file(os.path.join(self.template_dir, data)) as inline_template:
            yield ''.join(self._ProcessFunctions(inline_template.read()))
        else:
          yield '{{ %s %s }}' % (name, data)
      else:
        yield node

  @staticmethod
  def _SplitTags(template):
    """Splits a template string into static parts and tags to be replaced."""
    nodes = TEMPLATE_TAG.split(template)
    # First list contains static texts, second list contains template tags
    return nodes[::2], nodes[1::2]

  @staticmethod
  def _TagReplace(tags, replacements):
    """Replaces tags from a given `tags` iterable, using `replacements`.

    N.B. All <unicode> tags will be converted to utf8 byte strings.

    If a tag fails parsing at any point, due to bad tag-names, nonexisting keys
    or attributes, or a bad function name, the tag is returned verbatim.

    Arguments:
      @ tags: iter of str
        Strings that describe tags, indices and functions on them.
      @ replacements: dict
        Replacements

    Yields:
      str, replaced tag, or the original, unreplaced tag.
    """
    for tag in tags:
      parts = tag.split('|')
      needle_and_indices = parts[0].split(':')
      funcs = parts[1:]
      try:
        replacement = replacements[needle_and_indices[0]]
        for index in needle_and_indices[1:]:
          replacement = Parser._CollectFromIndex(replacement, index)
        if funcs:
          for func in funcs:
            replacement = TEMPLATE_FUNCTIONS[func](replacement)
        elif type(replacement) == SafeString:
          yield replacement
          continue
        else:
          replacement = TEMPLATE_FUNCTIONS['default'](replacement)

        # We will encode our returns down to utf8 byte strings.
        if type(replacement) == unicode:
          yield replacement.encode('utf8')
        else:
          yield replacement
      except (AttributeError, IndexError, KeyError):
        # AttributeError and IndexError originate from `CollectFromIndex`
        # KeyError is raised only at the beginning of this try block.
        yield '[%s]' % tag

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
    return self._Parse(self[template], replacements)

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
    return Template(self, template).Parse(**replacements)
    return self._Parse(self._PreParse(template), replacements)

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
  def __init__(self, parser, raw_template):
    super(Template, self).__init__()
    self.parser = parser
    print self.parser
    self.scopes = [self]
    self.Extend(raw_template)

  def __repr__(self):
    return '%s(%r)' % (type(self).__name__,
                       ', '.join('%s=%s' % item for item in vars(self)))

  @classmethod
  def FromFile(cls, parser, template_path):
    try:
      with file(template_path) as template:
        return cls(parser, template.read())
    except IOError:
      raise TemplateReadError('Cannot open: %r' % template_path)

  def Extend(self, template):
    scope_depth = len(self.scopes)
    nodes = TEMPLATE_FUNCTION.split(template)
    for index, node in enumerate(nodes):
      if index % 2:
        self._ExtendFunction(node)
      else:
        self._ExtendText(node)
    if len(self.scopes) != scope_depth:
      raise TemplateSyntaxError('Incorrect number of open scopes: %d' % len(self.scopes))

  def Parse(self, **kwds):
    output = []
    for tag in self:
      output.append(tag.Parse(**kwds))
    return SafeString(''.join(output))

  def _ExtendFunction(self, node):
    name, data = node.split(None, 1)
    if name == 'inline':
      self.AddTemplate(data)
    elif name == 'for':
      alias, _in, tag = data.split(None, 2)
      loop = TemplateLoop(self, tag, alias)
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
      else:
        self._AddPart(TemplateText(node))

  def _AddPart(self, item):
    self.scopes[-1].append(item)

  def AddTemplate(self, name):
    if self.parser is not None:
      for part in self.parser[name]:
        self._AddPart(part)
      return self.extend(self.parser[name])
    raise TemplateReadError('Cannot add template without a parser present.')

class TemplateLoop(list):
  def __init__(self, template, tag, alias):
    super(TemplateLoop, self).__init__()
    self.template = template
    self.tag = TemplateTag(tag)
    self.alias = alias

  def __repr__(self):
    return '%s(%r)' % (type(self).__name__, str(self))

  def __str__(self):
    'FOR %s IN %s' % (self.alias, self.tag)

  def Parse(self, **kwds):
    replacements = copy(kwds)
    for alias in self.tag.Get(**kwds):
      replacements[self.alias] = alias
      yield ''.join(tag.Parse(**replacements) for tag in self)


class TemplateTag(object):
  def __init__(self, name, indices=(), functions=None):
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
    tag_and_funcs = tag.split('|')
    name_and_indices = tag_and_funcs[0].split(':')
    return cls(name_and_indices[0], name_and_indices[1:], tag_and_funcs[1:])

  def Get(self, **kwds):
    try:
      return kwds[self.name]
    except KeyError:
      raise TemplateKeyError('No replacement with name %r' % self.name)

  def Parse(self, **kwds):
    if self.name not in kwds:
      return str(self)
    value = kwds[self.name]
    for index in self.indices:
      value = self._GetIndex(value, index)
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
