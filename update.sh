#!/bin/bash
export $(grep -v '#.*' .env | xargs) # load .env file
sudo docker build -t college_study .
curl -X POST $DOCKER_UPDATE_WEBHOOK