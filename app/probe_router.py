# app/probe_router.py
import inspect, traceback
from importlib import import_module

print("module:", import_module("app.langgraph_nodes.router"))
m = import_module("app.langgraph_nodes.router")
LangRouter_class = getattr(m, "LangRouter", None)
print("\nOBJECT NAME: LangRouter_class")
print("type:", type(LangRouter_class))

# If class exists, create an instance (if callable)
try:
    inst = LangRouter_class()
    print("\nInstance repr:", repr(inst))
except Exception as e:
    inst = None
    print("\nCould not instantiate LangRouter:", repr(e))
    traceback.print_exc()

# show members via inspect (more verbose than dir)
if inst is not None:
    print("\nINSPECT.getmembers (first 100):")
    members = inspect.getmembers(inst)
    for name, val in members[:200]:
        print(" ", name, "->", type(val))
    print("\n--- Trying to call the instance as a function ---")
    try:
        # call with simple args we expect (query, context)
        res = inst("hello test query", {})
        print("CALL OK, returned:", repr(res))
    except TypeError as te:
        print("TypeError on call:", te)
        traceback.print_exc()
    except Exception as exc:
        print("Exception on call:", repr(exc))
        traceback.print_exc()
else:
    print("\nNo instance available to inspect/call.")
