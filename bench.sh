#!/bin/sh
MAX=5
for i in `seq $MAX`; do
    echo "==== [${i}/${MAX}] ====="
    python3 nucleo-l152re.py
    cp /tmp/avatar_nucleo/test_log ./result/result_`date +"%Y%m%d"`_$i.txt
    sleep 5
done
