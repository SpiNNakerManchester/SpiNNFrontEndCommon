cmake_minimum_required(VERSION 2.8.12)
project(host_data_receiver)

find_package(PythonLibs)
include_directories(${PYTHON_INCLUDE_DIRS})

add_subdirectory(pybind11)
pybind11_add_module(host_data_receiver ../UDPConnection.cpp ../SDPHeader.cpp ../SDPMessage.cpp ../host_data_receiver.cpp)

