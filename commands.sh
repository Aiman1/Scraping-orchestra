#!/bin/bash
pip install playwright
python -m playwright install
gunicorn -b :$PORT slave:app  --timeout 360000 --preload
