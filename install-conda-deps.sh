#!/usr/bin/env bash
cd "$(dirname "$0")"

conda install qt6-main
conda install conda-forge::pyside6
conda install libopengl
pip install irview/lefdef-python/
pip install hammer/
conda install matplotlib
conda install pyqtgraph