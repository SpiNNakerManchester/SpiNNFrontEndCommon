#!/bin/bash

git clone --recursive https://github.com/bast/pybind11-demo
cd pybind11-demo
mkdir build
rm -f CMakeLists.txt
cp ../CMakeLists.txt ./
rm -f example.cpp
cd build
cmake ..
make
filename=$(find . -name "host_data_receiver*so")
mv $filename host_data_receiver.so
cp host_data_receiver.so ../../../../../../spinn_front_end_common/utility_models/
cd ../..
rm -rf pybind11-demo