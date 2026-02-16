#!/bin/bash

# Go to repo folder
#cd /path/to/your/stock_dashboard
cd /home/mohsen/Documents/stock_dashboard

# Pull latest changes
git reset --hard   # optional: discard local changes
git clean -fd      # optional: remove untracked files
git pull origin main
