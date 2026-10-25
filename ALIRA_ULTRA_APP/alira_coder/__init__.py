# Marks ALIRA_coder/ as a Python package purely so setuptools ships the
# compiled dist/ engine as package data. This directory is a Node.js
# project (see package.json) — nothing here is meant to be imported
# from Python; ALIRA_coder_integration.py only shells out to dist/run.js.
