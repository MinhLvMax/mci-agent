@echo off
cd /d "%~dp0"

set PYTHONPATH=%CD%

downloads\embed\python_embed\python.exe main.py

pause