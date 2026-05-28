"""
User-defined adapters for the adaptexts dataset browser.

Add your own adapters to the ADAPTERS list. Each entry is a tuple of:
    (display_name, adapter_id, adapter_instance)

  display_name  — shown in the browser UI
  adapter_id    — URL-safe identifier (lowercase, letters/digits/underscores, unique)
  adapter_instance — any object implementing AdapterInterface

The instance is iterated with `for ctx in adapter`, so __iter__ must yield
Context or ManyValuedContext objects with their .name attribute set.

Example
-------
    from mypackage.adapters import MyAdapter

    ADAPTERS = [
        ("My Custom Adapter", "my_adapter", MyAdapter(path="/data/contexts")),
    ]
"""

# from mypackage.adapters import MyAdapter

ADAPTERS: list[tuple[str, str, object]] = [
    # ("My Custom Adapter", "my_adapter", MyAdapter(...)),
]
