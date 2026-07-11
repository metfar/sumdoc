#!/bin/bash
for f in `find . -type f|grep -E ".git|__pycache__|build|.pytest_cache|.egg-info"|grep -v -E "gitrm|gitadd"`; do 
    echo git rm $f; 
done
