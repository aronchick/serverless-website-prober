#!/bin/bash
line=$(cat .env | awk '{print}' ORS=',')
aws lambda update-function-configuration --function-name EstuaryProber \
    --environment "Variables={$line}" --region=us-east-1