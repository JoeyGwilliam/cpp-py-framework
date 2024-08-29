import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import litgen
import pybind11
from pybind11 import setup_helpers
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

__version__ = "0.0.1"

_CPP_CMAKE_TEXT = '''add_library({cpp_namespace} STATIC {path_to_cpp} {path_to_header})
target_include_directories({cpp_namespace} PUBLIC ${{CMAKE_CURRENT_LIST_DIR}}/..)

# Under windows, auto __declspec(dllexport)
if (WIN32)
    set_target_properties(Example01 PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)
endif()
'''

_LITGEN_CMAKE_TEXT = '''set(litgen_cmake_help_message "

This Cmake module provides two public functions:


litgen_find_pybind11()
*******************************************************************************
litgen_find_pybind11() will find pybind11 and Python3
It is equivalent to:
    find_package(Python 3.8 REQUIRED COMPONENTS Interpreter Development[.Module])
    find_package(pybind11 CONFIG REQUIRED)
(after having altered CMAKE_PREFIX_PATH by adding the path to pybind11 provided
by `pip install pybind11`. This is helpful when building the C++ library outside of skbuild)

When building via CMake, you may have to specify Python_EXECUTABLE via
     -DPython_EXECUTABLE=/path/to/your/venv/bin/python


litgen_setup_module(bound_library python_native_module_name python_module_name)
*******************************************************************************
litgen_setup_module is a helper function that will:
* link the python native module (.so) to the bound C++ library (bound_library)
* set the install path of the native module to '.' (so that pip install works)
* automatically copy the native module to the python module folder after build
(so that editable mode works even when you modify the C++ library and rebuild)
* set the VERSION_INFO macro to the project version defined in CMakeLists.txt

")

# When building outside of skbuild, we need to add the path to pybind11 provided by pip
function(_lg_add_pybind11_pip_cmake_prefix_path)
    execute_process(
        COMMAND "${Python_EXECUTABLE}" -c
        "import pybind11; print(pybind11.get_cmake_dir())"
        OUTPUT_VARIABLE pybind11_cmake_dir
        OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ECHO STDOUT
        RESULT_VARIABLE _result
    )
    if(NOT _result EQUAL 0)
        message(FATAL_ERROR "
            Make sure pybind11 is installed via pip:
                pip install pybind11
            Also, make sure you are using the correct python executable:
                -DPython_EXECUTABLE=/path/to/your/venv/bin/python
        ")
    endif()
    set(CMAKE_PREFIX_PATH ${CMAKE_PREFIX_PATH} "${pybind11_cmake_dir}" PARENT_SCOPE)
endfunction()


function(litgen_find_pybind11)
    if(SKBUILD)
        # we only need the Development.Module component to build native modules
        find_package(Python 3.8 REQUIRED COMPONENTS Interpreter Development.Module)
    else()
        # when building via CMake, we need the full Development component,
        # to be able to debug the native module
        find_package(Python 3.8 REQUIRED COMPONENTS Interpreter Development)
    endif()
    set(Python_EXECUTABLE ${Python_EXECUTABLE} CACHE PATH "Python executable" FORCE)

    if(NOT SKBUILD)
        # when building via CMake, we need to add the path to pybind11 provided by pip
        # (skbuild does it automatically)
        _lg_add_pybind11_pip_cmake_prefix_path()
    endif()

    find_package(pybind11 CONFIG REQUIRED)
endfunction()


function(litgen_setup_module
    # Parameters explanation, with an example: let's say we want to build binding for a C++ library named "foolib",
    bound_library               #  name of the C++ for which we build bindings ("foolib")
    python_native_module_name   #  name of the native python module that provides bindings (for example "_foolib")
    python_module_name          #  name of the standard python module that will import the native module (for example "foolib")
    bindings_folder             # path to the folder containing the python bindings (for example "src/python_bindings")
                                # (used to deplay the native module to the python module folder after build in editable mode)
    )
    target_link_libraries(${python_native_module_name} PRIVATE ${bound_library})

    # Set python_native_module_name install path to "." (required by skbuild)
    install(TARGETS ${python_native_module_name} DESTINATION ${python_module_name})

    # Set VERSION_INFO macro to the project version defined in CMakeLists.txt (absolutely optional)
    target_compile_definitions(${python_native_module_name} PRIVATE VERSION_INFO=${PROJECT_VERSION})

    # Copy the python module to the src/python_bindings post build (for editable mode)
    set(bindings_module_folder ${bindings_folder}/${python_module_name})
    set(python_native_module_editable_location ${bindings_module_folder}/$<TARGET_FILE_NAME:${python_native_module_name}>)
    add_custom_target(
        ${python_module_name}_deploy_editable
        ALL
        COMMAND ${CMAKE_COMMAND} -E copy $<TARGET_FILE:${python_native_module_name}> ${python_native_module_editable_location}
        DEPENDS ${python_native_module_name}
    )
endfunction()
'''

_COMMON_CPP_PYBIND_INCLUDES = ('#include <pybind11/pybind11.h>\n'
                               '#include <pybind11/stl.h>\n'
                               '#include <pybind11/functional.h>\n'
                               '#include <pybind11/numpy.h>\n\n')

_LITGEN_GLUE_MARKER = (
    '// !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  AUTOGENERATED CODE !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n'
    '// <litgen_glue_code>  // Autogenerated code below! Do not edit!\n'
    '// </litgen_glue_code> // Autogenerated code end\n'
    '// !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  AUTOGENERATED CODE END !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n')

_LITGEN_PYDEF_MARKER = (
    '// !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  AUTOGENERATED CODE !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n'
    '// <litgen_pydef>  // Autogenerated code below! Do not edit!\n'
    '// </litgen_pydef> // Autogenerated code end\n'
    '// !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  AUTOGENERATED CODE END !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n')

_LITGEN_STUB_MARKER = (
    '# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  AUTOGENERATED CODE !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n'
    '# <litgen_stub>  // Autogenerated code below! Do not edit!\n'
    '# </litgen_stub> // Autogenerated code end\n'
    '# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  AUTOGENERATED CODE END !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n')

_PYI_IMPORTS = (
    'from typing import overload, List\n'
    'import numpy as np\n\n'

    'NumberType = (int, float, np.number)\n\n'
)

_CMAKE_TXT = '''cmake_minimum_required(VERSION 3.15...3.27)
project({py_package_name} VERSION "0.0.1")

set(CMAKE_CXX_STANDARD 20)

include(litgen_cmake.cmake)

# Build our example C++ library that we want to bind to python
add_subdirectory({path_to_src})

# Build a python module that provides bindings to the C++ library
#########################################################################
# litgen_find_pybind11 is defined in litgen_cmake/litgen_cmake.cmake
# and helps to find pybind11, whenever building with CMake or with pip / skbuild.
# When building with CMake, you may have to call cmake with -DPython_EXECUTABLE=/path/to/python
find_package(pybind11 REQUIRED)

# The python module sources
set(python_module_sources
    {path_to_module_cpp}                  # The python module entry point
    {path_to_cpp}          # The pybind11 bindings to the library, which are mainly auto-generated by litgen
)

# _daft_lib is the native python module that will be built by calling pybind11_add_module
# This will output a dynamic library called for example:
#     _daft_lib.cpython-312-darwin.so on macOS
#     _daft_lib.cpython-312-x86_64-linux-gnu.so on Linux
#     _daft_lib.cp312-win_amd64.pyd on Windows)
pybind11_add_module(_{py_package_name} ${{python_module_sources}})
# Call litgen_setup_module to generate the python wrapper around the native module
litgen_setup_module(
    # The C++ library for which we are building bindings
    {cpp_module_name}
    # The native python module name
    _{py_package_name}
    # This is the python wrapper around the native module
    {py_package_name}
    # path to the folder containing the python bindings (for example "src/python_bindings")
    # (used to deplay the native module to the python module folder after build in editable mode)
    ${{CMAKE_CURRENT_LIST_DIR}}
)

'''

_ENTRY_MODULE_TEXT = '''#include <pybind11/pybind11.h>

namespace py = pybind11;

void py_init_module_{py_package_name}(py::module& m);

PYBIND11_MODULE(_{py_package_name}, m)
{{
    py_init_module_{py_package_name}(m);
}}
'''


def convert_cpp_to_python_module(cpp_root_namespace: str,
                                 header_file: Path,
                                 input_cpp_file: Path,
                                 output_module_path: Path) -> None:
    """ Converts a c++ package to a python module. """
    output_module_path.mkdir(parents=True, exist_ok=True)

    options = litgen.LitgenOptions()
    options.namespaces_root = [cpp_root_namespace]  # The name of the root namespace in the c++ package
    output_module_name = output_module_path.name

    # Build folder structure
    build_folder = output_module_path / 'build'
    build_folder.mkdir(exist_ok=True)

    build_original_folder = build_folder / 'src_original'
    build_original_folder.mkdir(exist_ok=True)

    build_src_folder = build_folder / 'src'
    build_src_folder.mkdir(exist_ok=True)

    build_cpp_folder = build_src_folder / 'cpp'
    build_cpp_folder.mkdir(exist_ok=True)

    # Copy original c++ files
    shutil.copytree(header_file.parent, build_original_folder, dirs_exist_ok=True)

    build_cpp_path = build_cpp_folder / f"{output_module_name}.cpp"
    shutil.copy(header_file, build_cpp_folder)
    build_header_path = build_cpp_folder / header_file.name

    # Define positions for build files
    build_cmake_path = build_folder / "CMakeLists.txt"
    build_litgen_cmake_path = build_folder / "litgen_cmake.cmake"
    build_cpp_cmake_path = build_src_folder / "CMakeLists.txt"
    build_cpp_entry_point_path = build_cpp_folder / "module.cpp"
    output_stub_path = output_module_path / "__init__.pyi"

    with open(build_cmake_path, 'w') as f:
        f.write(_CMAKE_TXT.format(py_package_name=output_module_name,
                                  path_to_cpp=build_cpp_path.relative_to(build_folder).as_posix(),
                                  path_to_src=build_src_folder.relative_to(build_folder).as_posix(),
                                  path_to_module_cpp=build_cpp_entry_point_path.relative_to(build_folder).as_posix(),
                                  cpp_module_name=cpp_root_namespace))

    with open(build_cpp_entry_point_path, 'w') as f:
        f.write(_ENTRY_MODULE_TEXT.format(py_package_name=output_module_name))
    with open(build_litgen_cmake_path, 'w') as f:
        f.write(_LITGEN_CMAKE_TEXT)
    with open(build_cpp_cmake_path, 'w') as f:
        f.write(_CPP_CMAKE_TEXT.format(cpp_namespace=cpp_root_namespace,
                                       path_to_cpp=build_cpp_path.relative_to(build_src_folder).as_posix(),
                                       path_to_header=build_header_path.relative_to(build_src_folder).as_posix()))

    original_cpp_text = input_cpp_file.read_text()
    with open(build_cpp_path, 'w') as f:
        f.write(_COMMON_CPP_PYBIND_INCLUDES)
        f.write(f'namespace py = pybind11;\n\n')  # everyone does this... why?
        f.write(original_cpp_text)
        f.write(_LITGEN_GLUE_MARKER)
        f.write(f'void py_init_module_{output_module_name}'
                '(py::module& m) {\n\n')
        f.write(_LITGEN_PYDEF_MARKER)
        f.write('\n}')

    with open(output_stub_path, 'w') as f:
        f.write(_PYI_IMPORTS)
        f.write(_LITGEN_STUB_MARKER)

    litgen.write_generated_code_for_files(
        options=options,
        input_cpp_header_files=[str(build_header_path)],
        output_cpp_pydef_file=str(build_cpp_path),
        output_stub_pyi_file=str(output_stub_path),
    )
    pybind11_path = r"C:\Users\Joeyg\PycharmProjects\cpp-py-framework\.venv\Lib\site-packages\pybind11"

    pybind11_include_dir = pybind11.commands.get_include()
    python_include_dir = Path(sysconfig.get_path('include'))

    env = os.environ.copy()
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env["PATH"]

    subprocess.call(f'cmake -G "Visual Studio 17 2022" -DPython_EXECUTABLE={sys.executable} '
                    f'-DCMAKE_PREFIX_PATH={pybind11_path} ./', cwd=build_folder, env=env)

    shutil.copytree(pybind11_include_dir, build_folder / 'pybind11', dirs_exist_ok=True)
    shutil.copytree(python_include_dir, build_folder, dirs_exist_ok=True)

    subprocess.call(r'"C:\Program Files (x86)\Microsoft Visual '
                    r'Studio\2022\BuildTools\MSBuild\Current\Bin\msbuild.exe" py_example01.sln '
                    r'/p:Configuration=Release', cwd=build_folder, env=env)

    shutil.copy(build_folder / 'Release' / f'_{output_module_name}.cp311-win_amd64.pyd', output_module_path)

    with open(output_module_path / '__init__.py', 'w') as f:
        f.write(f'from ._{output_module_path.name} import *  # type: ignore # noqa: F403')

        shutil.rmtree(build_folder)


if __name__ == "__main__":
    repository_dir = Path(r'C:\Users\Joeyg\PycharmProjects\cpp-py-framework')
    include_dir = repository_dir / "src/Example01"

    cpp_root_namespace_01 = 'Example01'
    input_header_files_01 = include_dir / "Example01.h"
    input_cpp_file_01 = include_dir / "cpp/Example01.cpp"
    output_module_path_01 = repository_dir / "src/bindings/py_example01"

    convert_cpp_to_python_module(cpp_root_namespace_01, input_header_files_01, input_cpp_file_01, output_module_path_01)

    # must have installed pybind11 using:
    # git clone
    # cd pybind11
    # cmake -S . -B build
    # cmake --build build -j 2  # Build on 2 cores
    # cmake --install build
    # git clone https://github.com/pybind/pybind11.git
