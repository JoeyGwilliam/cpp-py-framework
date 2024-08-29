#include <memory>
#include <string>
#include <cmath>
#include <vector>
#include <algorithm>


namespace Example02
{
    // Simple add function
    // Args:
    //     a: the first number
    //     b: the second number
    //
    // Returns: The sum of the two ints
    int add(int a, int b);

    int add(int a, int b, int c); // And this is a separate docstring, for this overload

    // This is also a docstring,
    // on multiple lines
    inline int sub(int a, int b) { return a - b; }

    ////////////////////////////////////////////////////////////////////
    // Classes and structs bindings
    ////////////////////////////////////////////////////////////////////

    // A default constructor with named parameters will
    // be automatically generated in python for structs
    struct Point
    {
        int x = 0;  // The x value
        int y = 0;  // the y value
    };

    // A class will publish only its public methods and members
    class Widget
    {
    public:
        Widget() = default;
        int get_value() const { return m_value; }
        void set_value(int v) { m_value = v; }
    private:
        int m_value = 0;
    };

}
