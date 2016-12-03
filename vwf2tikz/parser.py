# Copyright 2016 Alba Mendez <me@alba.sh>
#
# This file is part of vwf2tikz.
#
# vwf2tikz is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# vwf2tikz is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with vwf2tikz.  If not, see <http://www.gnu.org/licenses/>.

from pyparsing import ZeroOrMore, Group, Optional, Suppress, Regex, Forward, dblQuotedString, removeQuotes
from .bdf2tikz.bdf2tikz.parser import ParseError


# Root parsing

def parse_vwf(input):
  # Decode in ASCII (FIXME)
  try:
    input = input.decode("ascii")
  except UnicodeDecodeError as e:
    raise ParseError(u"Non-ASCII content")

  # Remove starting comments, if present
  while True:
    input = input.lstrip()
    if input.startswith(u"/*"):
      input = input[2:]
      idx = input.find(u"*/")
      if idx == -1: raise ParseError(u"Unterminated comment")
      input = input[idx+2:]
    elif input.startswith(u"//"):
      input = input[2:]
      idx = input.find(u"\n")
      if idx == -1: idx = len(input)
      input = input[idx+1:]
    else: break

  # Low-level parsing
  parsed = ZeroOrMore(stanza).parseString(input, parseAll=True).asList()

  # TODO
  return parsed


# Low-level parsing (generic configuration language)

class Identifier(object):
  def __init__(self, s):
    self.s = s
  def __str__(self):
    return self.s
  def __repr__(self):
    return "<%s>" % (self.s,)

class Stanza(object):
  pass
class Block(Stanza):
  def __init__(self, field, index, contents):
    self.field = field
    self.index = index
    self.contents = list(contents)
  def __repr__(self):
    s = repr(self.field)
    if self.index != None: s += "[%s]" % repr(self.index)
    return "Block(%s, %s)" % (s, self.contents)
  def __str__(self):
    return self.__repr__()
class Assignment(Stanza):
  def __init__(self, field, value):
    self.field = field
    self.value = value
  def __repr__(self):
    return "(%s = %s)" % (repr(self.field), repr(self.value))
  def __str__(self):
    return self.__repr__()
class LevelStatement(Stanza):
  def __init__(self, level, time):
    self.level = level
    self.time = time
  def __repr__(self):
    return "Level(%s, %s)" % (self.level, self.time)
  def __str__(self):
    return self.__repr__()
class Comment(Stanza):
  pass

def _build_parser():
  identifier = Regex(r"[A-Za-z]+(_[A-Za-z]+)*").setParseAction(lambda t: Identifier(t[0]))
  string = dblQuotedString.setParseAction(removeQuotes)
  integer = Regex(r"-?\d+").setParseAction(lambda t: int(t[0]))
  decimal = Regex(r"-?\d+\.\d*").setParseAction(lambda t: float(t[0]))
  value = string | integer | decimal | identifier
  array = (value + ZeroOrMore(Suppress(",") + value)).setParseAction(lambda t: list(t))

  stanza = Forward()

  block = (identifier + Optional(Suppress("(") + value + Suppress(")")) + \
          Group(Suppress("{") + ZeroOrMore(stanza) + Suppress("}"))) \
          .setParseAction(lambda t: Block(*t))
  assignment = (identifier + Suppress("=") + (value | array) + Suppress(";")) \
               .setParseAction(lambda t: Assignment(*t))
  levelStatement = (Suppress("LEVEL") + integer + Suppress("FOR") + decimal + Suppress(";")) \
                   .setParseAction(lambda t: LevelStatement(*t))
  stanza << (block | assignment | levelStatement)
  return stanza

stanza = _build_parser()


# Header validation

# TODO


# Actual model

# TODO
