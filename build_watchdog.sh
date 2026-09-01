#!/bin/sh

docker build -t srcdocks:latest -t srcdocks:watchdog -f watchdog/Dockerfile .