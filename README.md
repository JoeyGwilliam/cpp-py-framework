# cpp-py-framework
A framework to follow for integrating c++ code into python with minimal time overhead. 

# Currently supported:
A single c++ package in the following format can be compiled into a python package:
```
NAMESPACE
-- NAMESPACE.h
-- src
     -- NAMESPACE.cpp
```

This can be done by calling 
```python
convert_cpp_to_python_module(NAMESPACE, 
                             PATH_TO_HEADER_FILE, 
                             PATH_TO_CPP_FILE,
                             PATH_TO_OUTPUT_PACKAGE)
```

The output package will have format:
```
MODULE_NAME
-- __init__.py
-- __init__.pyi
-- _MODULE_NAME.cp311-win_amd64.pyd
```

This can then be used as a normal package, including the typehints and docstrings provided in the .h header file:

```python
import PATH_TO_MODULE.MODULE_NAME as package
package.func()
```

# Requirements
Need to install MSVC build tools

and `pip install -r requirements.txt` believe it or not

Using python `3.11`. I think litgen requires `3.10` minimum