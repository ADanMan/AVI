#!/usr/bin/env python3
"""
Точка входа для валидационного пайплайна AVI

Использование:
    python validate.py
    python validate.py --only api
    python validate.py --skip docker
"""
from validation_pipeline.pipeline import main

if __name__ == "__main__":
    main()
