#!/bin/bash
eval $(egrep -v '^#' .env | xargs -d '\n') python3 main.py