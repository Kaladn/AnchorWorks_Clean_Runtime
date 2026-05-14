cmake_minimum_required(VERSION 3.24)

project(anchorworks_symbol_genome LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(anchorworks-symbol-genome
    src/symbol_genome_cli.cpp
)

if(MSVC)
    target_compile_options(anchorworks-symbol-genome PRIVATE /W4 /permissive-)
else()
    target_compile_options(anchorworks-symbol-genome PRIVATE -Wall -Wextra -Wpedantic)
endif()
