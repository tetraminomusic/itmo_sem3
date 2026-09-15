#!/bin/bash


scp -P 2222 src/* s502873@se.ifmo.ru:~/public_html/
open "https://se.ifmo.ru/~s502873/index.html"
