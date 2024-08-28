import shutil
import sys
from pathlib import Path

import litgen
from pybind11 import setup_helpers
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

__version__ = "0.0.1"

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

_CMAKE_TXT = '''cmake_minimum_required(VERSION 3.4...3.18)
project({py_package_name})

add_subdirectory(pybind11)
pybind11_add_module(cmake_example src/main.cpp)

# EXAMPLE_VERSION_INFO is defined by setup.py and passed into the C++ code as a
# define (VERSION_INFO) here.
target_compile_definitions(cmake_example
                           PRIVATE VERSION_INFO=${EXAMPLE_VERSION_INFO})
'''

def get_litgen_options(pckg_name: str) -> litgen.LitgenOptions:
    # configure your options here
    options = litgen.LitgenOptions()

    options.namespaces_root = [pckg_name]

    options.fn_exclude_by_name__regex = "^priv_"
    options.fn_params_exclude_names__regex = "^priv_"
    # The virtual methods of this class can be overriden in python
    options.class_override_virtual_methods_in_python__regex = "^Animal$"
    # will be published as: max_value_int and max_value_float
    options.fn_template_options.add_specialization("^MaxValue$", ["int", "float"], add_suffix_to_function_name=True)
    #  template<typename T> T MaxValue(const std::vector<T>& values);
    # will be published as: max_value_int and max_value_float
    options.fn_template_options.add_specialization("^MinValue$", ["int", "float"], add_suffix_to_function_name=False)
    # so we force the reference policy to be 'reference' instead of 'automatic'
    options.fn_return_force_policy_reference_for_references__regex = "Singleton$"
    # Since bool are immutable in python, we can to use a BoxedBool instead
    options.fn_params_replace_modifiable_immutable_by_boxed__regex = "^SwitchBoolValue$"
    # The functions in the MathFunctions namespace will be also published as vectorized functions
    options.fn_namespace_vectorize__regex = r"^DaftLib::MathFunctions$"  # Do it in this namespace only
    options.fn_vectorize__regex = r".*"  # For all functions
    options.python_run_black_formatter = True

    return options


def convert_cpp_to_python_module(cpp_root_namespace: str,
                                 input_header_files: list[Path],
                                 input_cpp_file: Path,
                                 output_module_path: Path) -> None:
    """ Converts a c++ package to a python module. """
    options = get_litgen_options(cpp_root_namespace)  # litgen.LitgenOptions()
    # options.namespaces_root = [cpp_root_namespace]  # The name of the root namespace in the c++ package

    output_module_name = output_module_path.name
    temp_cpp_folder = output_module_path / 'cpp'
    temp_cpp_folder.mkdir(exist_ok=True, parents=True)
    temp_cpp_path = temp_cpp_folder / f"{output_module_name}.cpp"
    for header_file in input_header_files:
        shutil.copy(header_file, temp_cpp_folder)

    output_stub_path = output_module_path / "__init__.pyi"

    original_cpp_text = input_cpp_file.read_text()
    with open(temp_cpp_path, 'w') as f:
        f.write(_COMMON_CPP_PYBIND_INCLUDES)
        f.write(f'namespace py = pybind11;\n\n')  # everyone does this... why?
        f.write(original_cpp_text)
        f.write(_LITGEN_GLUE_MARKER)
        f.write(f'void PyInit_{output_module_name}'
                '(py::module& m) {\n\n')
        f.write(_LITGEN_PYDEF_MARKER)
        f.write('\n}')

    with open(output_stub_path, 'w') as f:
        f.write(_PYI_IMPORTS)
        f.write(_LITGEN_STUB_MARKER)

    litgen.write_generated_code_for_files(
        options=options,
        input_cpp_header_files=[str(input_header_file) for input_header_file in input_header_files],
        output_cpp_pydef_file=str(temp_cpp_path),
        output_stub_pyi_file=str(output_stub_path),
    )

    sys.argv[1:] = ['install']  # To run the setup function

    ext_modules = [Pybind11Extension(output_module_name,
                                     [str(temp_cpp_path)],
                                     include_dirs=[str(temp_cpp_folder)],
                                     define_macros=[("VERSION_INFO", __version__)],
                                     )]
    setup(name=output_module_name, version=__version__, ext_modules=ext_modules, cmdclass={"build_ext": build_ext},
          python_requires=">=3.9", zip_safe=False  # Prevents egg creation
          )


if __name__ == "__main__":
    repository_dir = Path(r'C:\Users\Joeyg\PycharmProjects\cpp-py-framework\litgen_template')

    include_dir = repository_dir / "src/new_cpp_libraries"

    cpp_root_namespace_01 = 'DaftLib'
    input_header_files_01 = [include_dir / "DaftLib/DaftLib.h"]
    input_cpp_file_01 = include_dir / "DaftLib/cpp/DaftLib.cpp"
    output_module_path_01 = repository_dir / "src/python_bindings_new/daft_lib"

    #convert_cpp_to_python_module(cpp_root_namespace_01, input_header_files_01, input_cpp_file_01, output_module_path_01)

    import daft_lib
