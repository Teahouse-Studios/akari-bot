1. Comments
  - Do not add comments for code logic that is self-evident.
  - Comments should explain the "why" not the "what" or the implementation details.
  - Do not write comments unless the logic involves counter-intuitive edge cases, hacks, complex algorithms, or specific business rules.

2. Documentation
  - Documentation is intended for technical users and maintainers, not for beginners or those following tutorials.
  - Documentation should only cover functional overviews, basic usage steps, and interface implementations.
  - Do not provide step-by-step explanations of internal workings or technical details.
  - Do not add docstrings to modules, classes, or functions that are not part of the public API.

3. Localization
  - Localization text must be in Simplified Chinese only; do not provide translations for other languages.
  - Comments for configuration items are treated as documentation; describe their purpose only, not technical details.

4. Testing
  - `pytest` has poor compatibility; prioritize using the project's built-in `tests/run_one.py` test script.
  - The project contains a large number of unit tests; do not run the full test suite locally.
