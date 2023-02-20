# How to set patch rules

## 1. Patch rules

- In the `patch_flask_appbuilder.json` the following objects can be set
    - `patches`: the list of patch rules
    - `js`: the list of js files to be patched with replacement rules
    - `py`: the list of py files to be patched with replacement rules
- The patch rules are defined in the `patches` object
    - `file`: the file to be patched
    - `kind`: how to create the patch
- For js files, only replacement rules are supported
    - `kind`: not set
    - look at the js patch rules for details
        - in the `js` object, a list of rules to apply to the js files
        - the js file is the key for the replacement rules
        - the replacement rules are defined in the `rules` object
            - `original`: the string to be replaced
            - `patched`: the replacement string
- For py files, replacement rules works as for js files
    - `kind`: replace
    - look at the js patch rules for details
- when kind is set to `shadow`in the .py file case
    - the file is copied at the same path with original prepended to the file name
    - the patch file, user written, is copied at the same path (and then shadow the original file)

## 2. Writting Shadow code

- We use monkey patching to shadow the original code
- The shadow code is written in the file to be shadowed, original path but in the {pakage_name} folder
- It should import the original file `import flask_appbuilder.models.sqla.original_interface as patch_interface`
- It should provide some new function, variables, classes, etc.
- It should use all the original code with `sys.modules[__name__].__dict__.update(patch_interface.__dict__)`
- `patch_interface` is the name of the module that contains the original code
- `patch_interface` should be changed accordingly to the name of the original file
- to shadow a class or a function or a variable
    - write the new definition in the shadow file
    - assign the original definition to the new definition
    - example:
        ```python
        def apply_order_by(
            self,
            query: Query,
            order_column: Any,
            order_direction: str,
            aliases_mapping: Dict[str, AliasedClass] = None,
        ) -> Query:
            ...
            pass

        patch_interface.SQLAInterface.apply_order_by = apply_order_by
        ```
    - The assignements should be done at the end of the file, before the `sys.modules[__name__].__dict__.update(patch_interface.__dict__)` line
- be carrefull that monkey patching does not solve all the situation
    - For example, all objects created before the patching will not be affected by the patching
    - For classes, the patching is done on the class definition, not on the instances
    - If any reference to the original code is kept, the patching will not work unless you patch the reference too
- In some situation, reference to the package needs to be done and sometime, this leads to circular issues

# What is Monkey Patching?

According to ChatGPT, monkey patching is a way to modify the behavior of a module or class at runtime. It's a way to extend or override functionality without modifying the original source code.

In Python, monkey patching refers to the practice of modifying the behavior of an object or module at runtime by modifying its attributes or methods. 
Essentially, it means overriding or extending existing code at runtime, without modifying the original source code.

For example, let's say you have a function `add()` that adds two numbers:

```python
def add(a, b):
    return a + b
```
Now, suppose you want to change the behavior of `add()` to always add 5 to the result. You can achieve this by "monkey patching" the `add()` function:
    
```python
def new_add(a, b):
    return add(a, b) + 5

add = new_add
```
Now, any subsequent calls to `add()` will use the new version that adds 5 to the result. This can be useful in certain situations, such as when you need to temporarily modify the behavior of a module or function to fit your needs.

However, it's important to use monkey patching judiciously, as it can make code harder to understand and debug, especially when done in a large codebase with multiple developers. 

It's generally better to modify code directly, rather than relying on monkey patching, whenever possible.