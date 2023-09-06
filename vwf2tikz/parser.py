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

from functools import reduce
from pyparsing import ZeroOrMore, OneOrMore, Group, Optional, Suppress, Regex, Forward, QuotedString

class ParseError(Exception):
  def __init__(self, reason):
    Exception.__init__(self, "Malformed VWF file: %s" % (reason,))


# Root parsing

class Document(object):
  def __init__(self, header, signals, display_lines, time_bars):
    self.header = header
    self.signals = signals
    self.display_lines = display_lines
    self.time_bars = time_bars

def parse_vwf(input):
  # Decode in ASCII (FIXME)
  try:
    input = input.decode("ascii")
  except DecodeError as e:
    raise ParseError("Non-ASCII content")

  # Remove starting comments, if present
  while True:
    input = input.lstrip()
    if input.startswith("/*"):
      input = input[2:]
      idx = input.find("*/")
      if idx == -1: raise ParseError("Unterminated comment")
      input = input[idx+2:]
    elif input.startswith("//"):
      input = input[2:]
      idx = input.find("\n")
      if idx == -1: idx = len(input)
      input = input[idx+1:]
    else: break

  # Low-level parsing
  parsed = document.parseString(input, parseAll=True).asList()

  # Extract header
  header = validate_header(parsed)
  
  # Extract signals and transition lists, map them together producing Signal objects
  parsed, signals = consume_indexed_blocks(parsed, "SIGNAL")
  parsed, transition_lists = consume_indexed_blocks(parsed, "TRANSITION_LIST")
  signals = map_signals(signals, transition_lists)
  
  # Extract DISPLAY_LINE tree
  parsed, display_lines = consume_blocks(parsed, "DISPLAY_LINE")
  display_lines = map_display_lines(display_lines)
  
  # Extract time bars
  parsed, time_bars = consume_blocks(parsed, "TIME_BAR")
  # FIXME: validate

  # Extract groups
  parsed, groups = consume_indexed_blocks(parsed, "GROUP")
  # FIXME: validate, use in some way?

  if len(parsed):
    raise ParseError("Unexpected unparsed blocks in VWF:\n%s" % parsed)
  return Document(header, signals, display_lines, time_bars)


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
    self.contents = contents.asList()
  def __repr__(self):
    s = repr(self.field)
    if self.index != None: s += "[%s]" % repr(self.index)
    c = "".join(map(lambda x: "%s\n" % repr(x), self.contents))
    c = "".join("  " + line + "\n" for line in c.splitlines())
    return "Block(%s) {\n%s}" % (s, c)
  def __str__(self):
    return self.__repr__()
class Assignment(Stanza):
  def __init__(self, field, value):
    self.field = field
    self.value = value
  def __repr__(self):
    return "Assignment(%s = %s)" % (repr(self.field), repr(self.value))
  def __str__(self):
    return self.__repr__()
class LevelStatement(Stanza):
  def __init__(self, level, time):
    self.level = level
    self.time = time
  def __repr__(self):
    return "LevelStatement(%s, %s)" % (self.level, self.time)
  def __str__(self):
    return self.__repr__()
class Comment(Stanza):
  pass

def _build_parser():
  identifier = Regex(r"[A-Za-z]+(_[A-Za-z]+)*").setParseAction(lambda t: Identifier(t[0]))
  string = QuotedString('"', unquoteResults=True, multiline=True) # FIXME: escaping?
  integer = Regex(r"-?\d+").setParseAction(lambda t: int(t[0]))
  decimal = Regex(r"-?\d+\.\d*").setParseAction(lambda t: float(t[0]))
  value = string | decimal | integer | identifier
  array = (value + OneOrMore(Suppress(",") + value)).setParseAction(tuple)
  levelValue = integer | Regex(r"[X]")

  stanza = Forward()

  block = (identifier + Optional(Suppress("(") + value + Suppress(")"), default=None) + \
          Group(Suppress("{") + ZeroOrMore(stanza) + Suppress("}"))) \
          .setParseAction(lambda t: Block(*t))
  assignment = (identifier + Suppress("=") + (array | value) + Suppress(";")) \
               .setParseAction(lambda t: Assignment(*t))
  levelStatement = (Suppress("LEVEL") + levelValue + Suppress("FOR") + decimal + Suppress(";")) \
                   .setParseAction(lambda t: LevelStatement(*t))
  stanza << (block | assignment | levelStatement)
  return stanza

stanza = _build_parser()
document = ZeroOrMore(stanza) + Suppress(";")


# High-level parsing utilities

def consume_attributes(contents):
  """ Consumes (removes) Assignment stanzas from a block (among direct children only)
      and populates a dictionary with the values, leaving any other stanzas untouched. """
  attributes = {}
  def filter_stanza(stanza):
    if isinstance(stanza, Assignment):
      key, value = stanza.field.s, stanza.value
      if key in attributes: raise ParseError("Duplicate keys found in block:\n%s" % block)
      attributes[key] = value
      return False
    return True
  contents = list(filter(filter_stanza, contents))
  return contents, attributes

def validate_dictionary(attributes, mandatory_keys, optional_keys, strict=True):
  """ Verifies that a dictionary contains no unknown keys, and that several mandatory
      keys are present. Also tests for correct value type. If strict is set to False,
      unknown keys will be tolerated. """
  for key, value in attributes.items():
    expected = None
    if key in mandatory_keys: expected = mandatory_keys[key]
    elif key in optional_keys: expected = optional_keys[key]
    
    if strict and (expected is None):
      raise ParseError("Unknown field %s" % key)
    if not (expected is None):
      if not isinstance(value, expected):
        raise ParseError("Field %s has value '%s', expected type %s" % (key, value, expected))

  missing_keys = set(mandatory_keys).difference(set(attributes))
  if len(missing_keys):
    raise ParseError("Missing mandatory keys: %s" % (tuple(missing_keys), ))
  return attributes

def validate_attributes(block, mandatory_keys, optional_keys, strict=True):
  """ Convenience method for consuming attributes from a Block and then validating them. """
  block.contents, attributes = consume_attributes(block.contents)
  return validate_dictionary(attributes, mandatory_keys, optional_keys, strict)

def consume_indexed_blocks(contents, name):
  """ Consumes (removes) Block stanzas with the given name, from a block's direct children.
      Populates {index: contents} dictionary with removed stanzas. All matching blocks must have string indexes. """
  blocks = {}
  def filter_stanza(stanza):
    if isinstance(stanza, Block):
      bname, index, contents = stanza.field.s, stanza.index, stanza.contents
      if bname != name: return True
      if not isinstance(index, str): raise ParseError("Expected string index, found %s" % (index,))
      if index in blocks: raise ParseError("Duplicate index: %s" % index)
      blocks[index] = contents
      return False
    return True
  contents = list(filter(filter_stanza, contents))
  return contents, blocks

def consume_blocks(contents, name):
  """ Consumes (removes) Block stanzas with the given name, from a block's direct children.
      Returns list of "contents" properties for each removed stanza. All matching blocks must not have indexes. """
  blocks = []
  def filter_stanza(stanza):
    if isinstance(stanza, Block):
      bname, index, contents = stanza.field.s, stanza.index, stanza.contents
      if bname != name: return True
      if not (index is None): raise ParseError("Unexpected index on %s block: %s" % (name, index))
      blocks.append(contents)
      return False
    return True
  contents = list(filter(filter_stanza, contents))
  return contents, blocks


# Header validation

def validate_header(document):
  """ Validates and parses a header block. """
  if len(document) == 0: raise ParseError("Document has no stanzas")
  block = document.pop(0)
  if not (isinstance(block, Block) and block.field.s == "HEADER" and block.index is None):
    raise ParseError("First stanza is not a header block:\n%s" % block)

  header = validate_attributes(block, {
    "VERSION": int,
    "TIME_UNIT": Identifier,
    "DATA_OFFSET": float,
    "DATA_DURATION": float,
    "SIMULATION_TIME": float,
    "GRID_PHASE": float,
    "GRID_PERIOD": float,
    "GRID_DUTY_CYCLE": int,
  }, {
    "PRINT_OPTIONS": str,
  })
  if len(block.contents): return ParseError("Unparsed header contents:\n%s" % block)

  if not (header["VERSION"] == 1 and header["TIME_UNIT"].s == "ns" \
      and header["DATA_OFFSET"] == 0 and header["DATA_DURATION"] == header["SIMULATION_TIME"] \
      and header["GRID_DUTY_CYCLE"] == 50):
    return ParseError("Unaccepted header:\n%s" % header)
  return header


# Transition list parsing (and flattening)

def convert_level_stanza(stanza):
  """ Takes a stanza (either a LevelStatement, or a NODE Block) and
      returns a flattened list of (time, level) values. """
  if isinstance(stanza, LevelStatement):
    assert stanza.level in [0, 1, "X"]
    assert stanza.time > 0
    return [(stanza.time, stanza.level)]
  
  assert isinstance(stanza, Block) and stanza.field.s == "NODE" and (stanza.index is None)
  repeat = stanza.contents[0]
  assert isinstance(repeat, Assignment) and repeat.field.s == "REPEAT" and isinstance(repeat.value, int)
  
  contents = reduce(lambda c, stanza: c + convert_level_stanza(stanza), stanza.contents[1:], [])
  return contents * repeat.value


# Signal to transition list mapping

class Signal(object):
  def __init__(self, direction, value_type, width, parent):
    self.direction = direction
    self.value_type = value_type
    self.width = width
    self.parent = parent
    self.transition_list = None
  def __repr__(self):
    return "Signal(%s, %s, width=%d, parent=%s) [%s]" % (self.direction, self.value_type, self.width, repr(self.parent), repr(self.transition_list))
  def __str__(self):
    return self.__repr__()

def parse_signal(name, contents):
  contents, attributes = consume_attributes(contents)
  validate_dictionary(attributes, {
    "VALUE_TYPE": Identifier,
    "SIGNAL_TYPE": Identifier,
    "WIDTH": int,
    "LSB_INDEX": int,
    "DIRECTION": Identifier,
    "PARENT": str,
  }, {})
  assert len(contents) == 0

  value_type = attributes["VALUE_TYPE"].s
  signal_type = attributes["SIGNAL_TYPE"].s
  width = attributes["WIDTH"]
  lsb_index = attributes["LSB_INDEX"]
  direction = attributes["DIRECTION"].s
  parent = attributes["PARENT"]

  assert value_type in ["NINE_LEVEL_BIT"]
  assert {"SINGLE_BIT": False, "BUS": True}[signal_type] == (width != 1)
  assert lsb_index == {"SINGLE_BIT": -1, "BUS": 0}[signal_type]
  assert not (width > 1 and len(parent))
  assert width > 0
  if not len(parent): parent = None
  direction = {"OUTPUT": "output", "INPUT": "input", "BIDIR": "bidir"}[direction]

  return Signal(direction, value_type, width, parent)

def map_signals(signals, transition_lists):
  signals = {name: parse_signal(name, contents) for name, contents in signals.items()}
  for name, transition_list in transition_lists.items():
    assert name in signals
    assert len(transition_list) == 1
    signals[name].transition_list = transition_list[0]
  return signals


# DISPLAY_LINE tree mapping

class DisplayLine(object):
  def __init__(self, channel, radix, expanded, children):
    """ `channel` is the signal name this display line corresponds to.
        `expanded` is a boolean determining if children are shown.
        `children` is a list of DisplayLine children, or None if this is a leaf node. """
    self.channel = channel
    self.radix = radix
    self.expanded = expanded
    self.children = children
  def __repr__(self):
    out = "DisplayLine(%s, %s, expanded=%s)" % (repr(self.channel), self.radix, self.expanded)
    if not (self.children is None):
      lines = "".join(str(child) + "\n" for child in self.children)
      lines = "".join("  " + line for line in lines.splitlines(True))
      out += " {\n%s}" % lines
    return out
  def __str__(self):
    return self.__repr__()

def map_display_lines(blocks):
  """ Takes list of block contents (returned by consume_blocks, possibly)
      and returns list of top-level DisplayLine elements. """
  # First, parse each block and index in a dictionary so we can locate them faster
  display_lines = {}
  top_level_indexes = []
  for contents in blocks:
    contents, attributes = consume_attributes(contents)
    validate_dictionary(attributes, {
      "CHANNEL": str,
      "EXPAND_STATUS": Identifier,
      "RADIX": Identifier,
      "TREE_INDEX": int,
      "TREE_LEVEL": int,
    }, {
      "PARENT": int,
      "CHILDREN": tuple,
    })
    assert not len(contents)

    index = attributes["TREE_INDEX"]
    assert index not in display_lines
    display_lines[index] = attributes
    if "PARENT" not in attributes: top_level_indexes.append(index)

  # Starting from top-level items, recursively convert and remove entries from display_lines
  def convert(index, expected_parent=None, expected_level=0):
    attributes = display_lines[index]
    del display_lines[index]
    assert attributes["TREE_LEVEL"] == expected_level
    if expected_parent is None: assert "PARENT" not in attributes
    else: assert attributes["PARENT"] == expected_parent

    channel = attributes["CHANNEL"]
    radix = attributes["RADIX"].s
    expanded = {"COLLAPSED": False, "EXPANDED": True}[attributes["EXPAND_STATUS"].s]
    children = None
    if "CHILDREN" in attributes:
      children = [ convert(child, index, expected_level + 1) for child in attributes["CHILDREN"] ]

    return DisplayLine(channel, radix, expanded, children)
  
  result = list(map(convert, top_level_indexes))
  if len(display_lines): raise ParseError("There are orphan display lines: %s" % display_lines.values())
  return result

