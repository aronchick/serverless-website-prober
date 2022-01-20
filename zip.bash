#! /bin/bash

mkdir -p tf/package
cd tf/build/$1
zip -r9 ../../package/$1.zip .
