#!/bin/bash
cd tf

declare -a regions=( "ap-south-1" "eu-west-1" "us-east-1" "us-west-1" )
for r in "${regions[@]}"
do
	terraform workspace select "$r"
    terraform apply -auto-approve
done