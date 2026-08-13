# Third-Party Notices

Writing Tools is distributed under the GNU General Public License v3.0. Its
Python dependencies remain subject to their own licenses. The table below lists
the direct dependencies pinned by the Windows/Linux build; transitive packages
and their license metadata are available in each installed Python distribution.

| Package | Version | License | Project |
|---|---:|---|---|
| cryptography | 50.0.0 | Apache-2.0 OR BSD-3-Clause | https://github.com/pyca/cryptography |
| darkdetect | 0.8.0 | BSD-3-Clause | https://github.com/albertosottile/darkdetect |
| google-genai | 2.12.1 | Apache-2.0 | https://github.com/googleapis/python-genai |
| markdown2 | 2.5.5 | MIT | https://github.com/trentm/python-markdown2 |
| ollama | 0.6.2 | MIT | https://github.com/ollama/ollama-python |
| openai | 2.46.0 | Apache-2.0 | https://github.com/openai/openai-python |
| PyInstaller | 6.21.0 | GPL-2.0-or-later with bootloader exception | https://github.com/pyinstaller/pyinstaller |
| pynput | 1.8.2 | LGPL-3.0 | https://github.com/moses-palmer/pynput |
| pyperclip | 1.11.0 | BSD | https://github.com/asweigart/pyperclip |
| PySide6 / Qt for Python | 6.8.3 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | https://pyside.org |

## SharpInput-derived workflow

The Prompt Workbench adapts the behavioral contract and workflow concepts from
[gaoyechen/SharpInput](https://github.com/gaoyechen/SharpInput) v3.3. SharpInput
Reference snapshot: `0d23ef15682ac2bc05d4954546900ad0a117ee1b`. The
desktop workflow is a project-specific reimplementation; SharpInput is not
installed as a runtime dependency. SharpInput is distributed under the
following MIT License:

```text
MIT License

Copyright (c) 2026 gaoyechen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Binary distributors should preserve this notice, the repository `LICENSE`, and
the license files shipped by the corresponding Python wheels. This document is
informational and is not legal advice.
