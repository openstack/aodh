#!/bin/bash
set -e

if [ "$1" = "--coverage" ]; then
	COVERAGE_ARG="$1"
	shift
fi

export AODH_TEST_STORAGE_URL="hbase://__test__"

# Yield execution to venv command
$*
