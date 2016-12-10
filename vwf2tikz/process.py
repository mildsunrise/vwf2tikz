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

from . import parser, render
from .parser import parse_vwf

default_options = {
  "scale": 1310000/2, "viewport": False,
  "time_digits": 3,

  "clock_node": "clk", "clock_no_slope": True, "clock_lines": "rising",
  "render_grid": False,

  "render_bit_as_bus": False,
  "render_hex_prefix": True, "render_hex_uppercase": True, "render_hex_zero_padding": True,
  
  "disable_propagation_in_binary": True, "join_unknown": True,

  "extra_args": [],
  "custom_renderers": {},
}

def render_vwf(rs, options):
  rs = parse_vwf(rs)
  lines = render.get_rendered_lines(rs.display_lines, options)
  
  def render_line(line):
    name = render.render_line_name(line, options)
    content = render.render_display_line(line, rs.signals, options)
    return name + " & " + content + " \\\\\n"
  output = "".join(map(render_line, lines))
  return output
