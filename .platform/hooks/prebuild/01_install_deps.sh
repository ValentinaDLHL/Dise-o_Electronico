#!/bin/bash
yum update -y
yum install -y gcc python3-devel postgresql-devel
pip3 install --upgrade pip
pip3 install --no-cache-dir -r /var/app/staging/requirements.txt
