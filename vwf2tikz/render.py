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

import types
from .bdf2tikz.bdf2tikz.render import RenderError, render_node_name, render_tikz_text
from . import parser


# Utilities for level lists

def zip_level_lists(lists):
  """ 'Zip' many lists of levels into a single list: (time, (level1, level2, ...)).
      Given lists will be modified in place, and will be empty if all lists have
      the same duration. If duration differs, only the common time will be consumed. """
  assert len(lists)
  result = []
  # Keep consuming while all lists have items
  while reduce(lambda r, levels: r and len(levels), lists, True):
    time = min(levels[0][0] for levels in lists)
    levels = tuple(levels[0][1] for levels in lists)
    result.append((time, levels))
    for levels in lists:
      levels[0] = (levels[0][0] - time, levels[0][1])
      if levels[0][0] == 0: levels.pop(0)
  return result

def crop_level_list(levels, viewport):
  """ Crops a level list to a specified (start, end) time range. """
  start, duration = viewport[0], viewport[1] - viewport[0]
  result = []
  for time, level in levels:
    assert time >= 0
    if start > 0:
      start -= time
      if start >= 0: continue
      time = -start
    if time > duration: time = duration
    if duration == 0: break
    result.append((float(time), level))
    duration -= time
  return result

def bits_to_int(x):
  """ Transform a logic vector like (1,0,1,1) into an integer like 11. """
  def reduce_bit(accum, bit):
    assert bit in [0, 1]
    return accum * 2 + bit
  return reduce(reduce_bit, x)


# Native renderers

NATIVE_RENDERERS = {}

def render_unsigned_decimal(line, config):
  def renderer(x):
    return str(bits_to_int(x))
  return renderer

NATIVE_RENDERERS["Unsigned"] = render_unsigned_decimal

def render_signed_decimal(line, config):
  def renderer(x):
    res = bits_to_int(x)
    if x[0]: res -= (1 << len(x))
    return str(res)
  return renderer

NATIVE_RENDERERS["Signed"] = render_signed_decimal

def render_hexadecimal(line, config):
  def renderer(x):
    res = "%x" % bits_to_int(x)
    if config["render_hex_zero_padding"]:
      while len(res) * 4 < len(x): res = "0" + res
    if config["render_hex_uppercase"]: res = res.upper()
    if config["render_hex_prefix"]: res = "0x" + res
    return res
  return renderer

NATIVE_RENDERERS["Hexadecimal"] = render_hexadecimal

def render_bit_string(line, config):
  def renderer(x):
    return "".join(str(bit) for bit in x)
  return renderer

NATIVE_RENDERERS["Binary"] = render_bit_string

def render_ascii(line, config):
  SPECIAL = ur'''
NUL
SOH
STX
ETX
EOT
ENQ
ACK
BEL
BS
HT
LF
VT
FF
CR
SO
SI
DLE
DC1
DC2
DC3
DC4
NAK
SYN
ETB
CAN
EM
S2
ESC
FS
GS
RS
US
  '''.strip().splitlines()
  def represent(i):
    assert i < 128
    if i < len(SPECIAL):
      return SPECIAL[i]
    if i == 127:
      return "DEL"
    return "'%c'" % i
  mapping = {i: represent(i) for i in xrange(128)}
  return lambda x: mapping[bits_to_int(x)]

NATIVE_RENDERERS["ASCII"] = render_ascii


# Determine which display lines to actually render, and node matching logic

def get_rendered_lines(display_lines, config):
  """ Get list of display lines to render, honoring "expanded" attribute. """
  rendered = []
  def process_line(line):
    rendered.append(line)
    if line.children and line.expanded:
      for child in line.children: process_line(child)
  for line in display_lines: process_line(line)
  return rendered

def match_node(pattern, node):
  """ Generic function to match a config option (i.e. clock_node)
      with a node name. Returns True if positive match. """
  if isinstance(pattern, str) or isinstance(pattern, unicode):
    return pattern == node
  if isinstance(pattern, tuple) or isinstance(pattern, list):
    return node in pattern
  if isinstance(pattern, types.FunctionType):
    return pattern(node)
  return False


# Actual rendering logic

def get_level_list(line, signals):
  """ Read the corresponding flattened level list from a leaf display line. """
  assert line.children is None
  stanza = signals[line.channel].transition_list
  return parser.convert_level_stanza(stanza)

def get_line_level_lists(line, signals, config):
  """ Get level lists for a display line. Returns either a
      single level list, or a tuple of level lists, depending
      on whether it's a bus or single line, and the `clock_node` and
      `render_bit_as_bus` options. """
  # if it's a bus, it's rendered as a bus no matter what
  if not (line.children is None):
    return tuple(get_level_list(child, signals) for child in line.children)
  
  # is it the clock node? then always render as bit
  if match_node(config["clock_node"], line.channel):
    return get_level_list(line, signals)

  # does it match render_bit_as_bus? then, bus
  if match_node(config["render_bit_as_bus"], line.channel):
    return (get_level_list(line, signals),)
  
  # render as bit
  return get_level_list(line, signals)

def prepare_level_list(level_list, line, config):
  """ Prepare the output of get_line_level_lists into a single
      (possibly zipped) level list, ready for render. This includes
      propagating unknown values, joining etc. """
  # first, zip the level lists if this is a bus
  is_bus = isinstance(level_list, tuple)
  if is_bus: level_list = zip_level_lists(level_list)
  
  # propagate unknown values
  def map_value(v):
    if not isinstance(v, tuple): return v
    # FIXME propagate / join unknowns, honoring config
    return v
  level_list = list((t, map_value(v)) for t, v in level_list)
  
  return level_list

def create_renderer(line, config):
  """ Construct a renderer for a given display line. """
  for pattern, constructor in config["custom_renderers"].items():
    if match_node(pattern, line.channel): return constructor(line, config)
  return NATIVE_RENDERERS[line.radix](line, config)

def render_level(time, level, renderer, config):
  """ Render a level value into a tikz-timing character. """
  mappings = {0: "L", 1: "H"}
  if level in mappings: return mappings[level]
  
  assert isinstance(level, tuple)
  content = renderer(level)
  length = min(len(content), config["render_hide_char_limit"])
  length = length * config["render_hide_char_scale"] + config["render_hide_margin"]
  if time / config["scale"] < length: content = ""
  return "D{%s}" % (content,)

def create_time_formatter(config):
  scale = config["scale"]
  def format_time(time):
    # FIXME: round to N digits, and keep track of accumulated error
    result = "%f" % (time / scale)
    while result.endswith("0"): result = result[:-1]
    if result.endswith("."): result = result[:-1]
    return result
  return format_time

def render_level_list(level_list, line, config):
  """ Render a prepared level list, into a sequence of tikz-timing
      characters. Honors scale and viewport. """
  # crop if viewport specified in config
  if config["viewport"]:
    level_list = crop_level_list(level_list, config["viewport"])

  if not len(level_list): return ""
  
  # render!
  renderer = create_renderer(line, config)
  format_time = create_time_formatter(config)
  return " ".join(format_time(time) + render_level(time, level, renderer, config) for time, level in level_list)

def render_clock_level_list(level_list, line, config):
  # crop if viewport specified in config
  if config["viewport"]:
    level_list = crop_level_list(level_list, config["viewport"])
  
  format_time = create_time_formatter(config)
  if not len(level_list): return ""
  
  # render first level explicitely
  first_time, last_level = level_list.pop(0)
  assert last_level in [0, 1]
  result = format_time(first_time) + render_level(first_time, last_level, None, config)
  
  # render rest of levels
  for time, level in level_list:
    assert level in [0, 1] and level != last_level
    result += " " + format_time(time) + "C"
    last_level = level
  
  return result

def render_display_line(line, signals, config):
  """ Convenience function. Renders a display line into a sequence of tikz-timing characters. """
  level_list = get_line_level_lists(line, signals, config)
  is_bus = isinstance(level_list, tuple)
  
  level_list = prepare_level_list(level_list, line, config)
  
  if (not is_bus) and match_node(config["clock_node"], line.channel) and config["clock_no_slope"]:
    return render_clock_level_list(level_list, line, config)
  
  return render_level_list(level_list, line, config)


# Name rendering

def render_line_name(line, config):
  # TODO: maybe fix incomplete names
  return render_node_name(line.channel, {})


# Help lines rendering

def get_clock_lines(help_lines, display_lines, signals, config):
  if not config["clock_lines"]: return
  target = {"rising": 1, "falling": 0}[config["clock_lines"]]
  
  for line in display_lines:
    if not match_node(config["clock_node"], line.channel): continue
    # assuming level list is well formed (no consecutive tuples with same level, only 0 and 1)
    accum_time = 0
    for time, level in get_level_list(line, signals):
      if level == target: help_lines.add(accum_time)
      accum_time += time

def render_help_lines(help_lines, config):
  if config["viewport"]:
    start, end = config["viewport"]
    help_lines = (t - start for t in filter(lambda t: start < t < end, help_lines))
  arg = ",".join(map(lambda t: create_time_formatter(config)(t), help_lines))
  return "\\vertlines[help lines]{%s}" % arg
