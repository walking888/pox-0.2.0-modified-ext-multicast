#! /bin/bash

gcc -c -fPIC gf256.c
gcc -shared gf256.o -o libgf256.so
