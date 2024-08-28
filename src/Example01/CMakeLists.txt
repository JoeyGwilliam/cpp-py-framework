add_library(Example01 STATIC cpp/Example01.cpp Example01.h)
target_include_directories(Example01 PUBLIC ${CMAKE_CURRENT_LIST_DIR}/..)

set(CMAKE_CXX_STANDARD 14 CACHE STRING "C++ version selection")  # or 11, 14, 17, 20
set(CMAKE_CXX_STANDARD_REQUIRED ON)  # optional, ensure standard is supported
set(CMAKE_CXX_EXTENSIONS OFF)  # optional, keep compiler extensions off
find_package(pybind11 CONFIG REQUIRED)
# or add_subdirectory(pybind11)

pybind11_add_module(Example01 Example01.cpp)
# Under windows, auto __declspec(dllexport)
if (WIN32)
    set_target_properties(Example01 PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)
endif()
