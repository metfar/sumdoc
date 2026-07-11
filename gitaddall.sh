#!/bin/bash
for f in `find . -type f|grep -v .git|grep -v __pycache__ |grep -v build|grep -v .pytest_cache`; do 
    echo git add $f; 
done
