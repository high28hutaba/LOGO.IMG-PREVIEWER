@echo off
title LOGO.IMG PREVIEW TOOL
echo Installing requirements.txt
pip install -r requirements.txt
python -m pip install pillow
echo Openning preview.py
python preview.py
echo closed Python
pause