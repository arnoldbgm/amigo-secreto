#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Node.js dependencies
# npm install

# # Build Tailwind CSS
# npm run build:css

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
