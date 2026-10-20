@echo off
setlocal
"%~dp0.venv-litellm\Scripts\litellm.exe" %*
exit /b %errorlevel%
