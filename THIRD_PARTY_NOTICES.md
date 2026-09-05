# Third-party notices

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
