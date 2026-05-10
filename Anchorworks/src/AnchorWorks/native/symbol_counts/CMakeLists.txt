cmake_minimum_required(VERSION 3.24)

project(anchorworks_symbol_counts LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(awsc_core STATIC
    src/awsc.cpp
)

target_include_directories(awsc_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

if(MSVC)
    target_compile_options(awsc_core PRIVATE /W4 /permissive-)
else()
    target_compile_options(awsc_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_executable(anchorworks-symbol-counts
    src/awsc_cli.cpp
)

target_link_libraries(anchorworks-symbol-counts PRIVATE awsc_core)

if(MSVC)
    target_compile_options(anchorworks-symbol-counts PRIVATE /W4 /permissive-)
else()
    target_compile_options(anchorworks-symbol-counts PRIVATE -Wall -Wextra -Wpedantic)
endif()
