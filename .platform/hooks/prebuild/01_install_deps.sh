#!/bin/bash
set -e

echo "Actualizando pip, setuptools y wheel..."
sudo pip3 install --upgrade pip setuptools wheel

echo "Instalando dependencias desde requirements.txt..."
sudo pip3 install -r requirements.txt
