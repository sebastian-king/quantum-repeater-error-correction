#!/usr/bin/env sh
TEST_PIDS=$(ps aux | grep python | grep -E "_simqtest" | awk {'print $2'})
if [ "$TEST_PIDS" != "" ]
then
        kill -9 $TEST_PIDS
fi
