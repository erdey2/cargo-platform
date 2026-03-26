#!/usr/bin/env bash

# Upgrade pip
pip install --upgrade pip

# Install Python packages
pip install -r requirements/production.txt

# Collect static files and run migrations
python manage.py collectstatic --noinput
python manage.py migrate
