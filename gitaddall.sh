#!/bin/bash
for f in `find . -type f|grep -v .git|grep -v __pycache__ |grep -v build|grep -v .pytest_cache|grep -v .egg-inf|grep -v .egg-info`; do 
    echo git add $f; 
done
