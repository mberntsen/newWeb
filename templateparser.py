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
TAGSPLITTER = re.compile(r'\[([\w:|]+)\]')


class Error(Exception):
  """Superclass used for inheritance and external exception handling."""


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
      try:
        template_path = os.path.join(self.template_dir, template)
        self[template] = file(template_path).read()
      except IOError:
        raise TemplateReadError('Cannot open: %r' % template_path)
    return super(Parser, self).__getitem__(template)

  def __setitem__(self, key, value):
    """Writes the template parts to the given key."""
    super(Parser, self).__setitem__(key, self._SplitTags(value))

  @staticmethod
  def _CollectFromIndex(replacement, index):
    """Gathers the `index` from the `replacement` by index, key or attribute.

    Arguments:
      @ replacement: obj
        The replacement object, iterable, mapping or any kind of object.
      @ index: str
        The index, key or attribute name to find on the replacement.

    Raises:
      IndexError: the int()'ed `index` does not exist on the `replacement`.
      AttributeError: resulting error if the `index` does not exist in any form.

    Returns:
      str, the string contained on the `index` of the replacement.
      """
    try:
      # Assume integer-indexable object (list, mapping).
      return replacement[int(index)]
    except (TypeError, ValueError):
      # ValueError: int() call failed, index is a string.
      # TypeError: int() call succeeded, but source object is unsubscriptable.
      try:
        return replacement[index]
      except (KeyError, TypeError):
        # KeyError, index definitely not a key, but can still be an attributes.
        # TypeError: source object is unsubscriptable.
        return getattr(replacement, index)

  @staticmethod
  def _Parse(template, replacements):
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
        (iter(texts), Parser._TagReplace(tags, replacements)))))

  @staticmethod
  def _SplitTags(template):
    """Splits a template string into static parts and tags to be replaced."""
    nodes = TAGSPLITTER.split(template)
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
    return self._Parse(self[template], replacements)

  @staticmethod
  def ParseString(template, **replacements):
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
    return Parser._Parse(Parser._SplitTags(template), replacements)

  @staticmethod
  def RegisterFunction(name, function):
    """Registers a templating `function`, allowing use in templates by `name`.

    Arguments:
      @ name: str
        The name of the template function. This can be used behind a pipe ( | )
      @ function: function
        The function that should be used. Ideally this returns a string.
    """
    TEMPLATE_FUNCTIONS[name] = function

  TemplateReadError = TemplateReadError

class SafeString(str):
  """A template string, which has had all its processing done already."""


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


TEMPLATE_FUNCTIONS = {
        'default': HtmlEscape,
        'html': HtmlEscape,
        'raw': lambda x: x,
        'url': urllib.quote_plus}
