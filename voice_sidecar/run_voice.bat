@echo off
rem Starts the voice sidecar from its own virtual environment (see README for setup).
cd /d "%~dp0"
".venv\Scripts\python.exe" -m tarkov_voice --config voice.toml %*
