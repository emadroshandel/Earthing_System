# Third-party notices

Earthing System itself is licensed under the GNU General Public License, version 3
or later (see `LICENSE`). The components listed below are third-party works
under their own licences, which are reproduced here. All of them are
GPL-compatible, so the combined work may be distributed under the GPL.

## Plotly.js — `web/vendor/plotly.min.js`

Version 2.35.2, bundled so that the application works with no internet
connection. Plotly.js is released under the MIT License.

> Copyright (c) 2012-2024 Plotly, Inc.
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the above copyright notice and this permission
> notice being included in all copies or substantial portions of the Software.

Source: https://github.com/plotly/plotly.js

## three.js — `web/vendor/three/`

Version 0.182.0 (`three.module.min.js`, `three.core.min.js` and
`addons/controls/OrbitControls.js`), bundled so that the 3-D electrode view
works with no internet connection. three.js is released under the MIT License
(full text in `web/vendor/three/LICENSE`).

> The MIT License
>
> Copyright © 2010-2025 three.js authors
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in
> all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
> THE SOFTWARE.

Source: https://github.com/mrdoob/three.js

## Pyodide — loaded from a CDN in browser mode only

The online demo loads Pyodide (CPython compiled to WebAssembly) from
`cdn.jsdelivr.net` at run time. Pyodide is released under the Mozilla Public
License 2.0. No Pyodide code is redistributed in this repository.

Source: https://github.com/pyodide/pyodide

## NumPy — optional dependency

Installed by the user with `pip`, or loaded by Pyodide in browser mode.
BSD 3-Clause License. Not redistributed here.

## Standards

This software implements calculation methods published in IEEE and IEC
standards, and reproduces the numerical constants those methods require
(material properties, tabulated coefficients, limit values), each with a
citation to the clause it comes from.

It does **not** reproduce the text, figures, commentary or tables of any
standard, and it is **not** a substitute for them. Anyone using this software
for real design work must hold and read the applicable standards themselves.
No endorsement by IEEE, IEC, BSI or any other standards body is claimed or
implied.
