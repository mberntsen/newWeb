# Originally from: http://code.activestate.com/recipes/577202/#c4
# Written by Vasilij Pupkin (2012)
# Minor changes by Elmer de Looff (2012)
# Licensed under the MIT License (http://opensource.org/licenses/MIT


class ALIGN(object):
  LEFT, RIGHT = '-', ''

class Column(list):
  def __init__(self, name, data, align=ALIGN.LEFT):
    list.__init__(self, data)
    self.name = name
    self.width = max(len(x) for x in self + [name])
    self.format = ' %%%s%ds ' % (align, self.width)

class Table(object):
  def __init__(self, *columns):
    self.columns = columns
    self.length = max(len(x) for x in columns)

  def get_row(self, i=None):
    for x in self.columns:
      if i is None:
        yield x.format % x.name
      else:
        yield x.format % x[i]

  def get_line(self):
    for x in self.columns:
      yield '-' * (x.width + 2)

  def join_n_wrap(self, char, elements):
    return ' ' + char + char.join(elements) + char

  def get_rows(self):
    yield self.join_n_wrap('+', self.get_line())
    yield self.join_n_wrap('|', self.get_row(None))
    yield self.join_n_wrap('+', self.get_line())
    for i in range(0, self.length):
      yield self.join_n_wrap('|', self.get_row(i))
    yield self.join_n_wrap('+', self.get_line())

  def __str__(self):
    return '\n'.join(self.get_rows())
