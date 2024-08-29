add_library(Example01 STATIC py_example01.cpp Example01.h)
target_include_directories(Example01 PUBLIC ${CMAKE_CURRENT_LIST_DIR}/..)

# Under windows, auto __declspec(dllexport)
if (WIN32)
    set_target_properties(Example01 PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)
endif()
