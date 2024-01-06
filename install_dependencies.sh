#!/bin/bash

# install apt packages
sudo apt install -y $(cat apt-packages.txt)

# bat is instlled as "batcat" symlink it to bat
sudo ln -s /usr/bin/batcat /usr/bin/bat

# install python dependencies
python3 -m pip install -r requirements.txt
