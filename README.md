# vwf2tikz

Program that reads Quartus Vector Waveform files (`.vwf` extension) and emits LaTeX
code that uses TikZ (and the `tikz-timing` package) to create a timing diagram
representing it. This graphic can then be embedded in documents.

This is a sister project of [bdf2tikz](https://github.com/mildsunrise/bdf2tikz),
which renders schematic files using TikZ, and actually calls some of its code
for rendering.

The program can generate one of:

 - LaTeX source for a minimal complete document (using the `standalone` class).
 - LaTeX code for the graphic (i.e. to be `\input` into a document).
 - `tikz-timing` table characters (i.e. to be `\input` inside a `tikztimingtable` environment).

The third one allows for maximum control, you can supply your own TikZ styles.
The second and first ones will use a template with predefined styles, which can
be seen at `template.tex`.

In the first case, this will all be wrapped inside a `standalone` document with
a second template that can be seen at `document.tex`.

Main features:

 - Adjustable scale and viewport.
 - Support both single bit nodes as well as buses.
 - Supports and obeys all Quartus options for rendering bus values, user can also define custom value renderers.
 - Optional special rendering for clock (no slope and/or vertical lines on rising edges).
 - Obeys state in which the `.vwf` was closed (collapsed nodes won't be rendered).
 - Understands "unknown" states on bits and buses.
 - Customizable rendering for node names (inherited from bdf2tikz).
 - Optional rendering of the time grid.
 - Customizable number formatting.
 - Hides labels from data nodes that are too small.
 - Add extra TikZ arguments, global and per-row.

Rendering of time scale grid (using actual units) still a TODO.

## Install

This program needs the `pyparsing` module to be available. Install with:

    pip install pyparsing

However, you need a LaTeX distribution installed in order to compile the
resulting code into a PDF. The code only has dependencies with TikZ and
the `tikz-timing` package.

The template also depends on the `amsmath` package.

## Usage

    python main.py <VWF file> out.tex

Note that `main.py` can also be used as a module for programmatic rendering.
(Option parsing is still pending.)
