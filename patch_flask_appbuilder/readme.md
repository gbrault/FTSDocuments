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