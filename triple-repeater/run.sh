#!/bin/sh

python3 repeater1_simqtest.py &
python3 repeater2_simqtest.py &
python3 repeater3_simqtest.py &
python3 bob_simqtest.py &
python3 alice_simqtest.py
