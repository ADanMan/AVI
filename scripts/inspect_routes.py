#!/usr/bin/env python3
"""
Script to inspect all registered routes in FastAPI app
"""
import sys
from pathlib import Path


# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from api.routes import router

    print("=" * 80)
    print("REGISTERED ROUTES IN FASTAPI APP")
    print("=" * 80)
    print()

    # Collect all routes
    routes = []

    def collect_routes(r, prefix=""):
        """Recursively collect routes from router"""
        for route in r.routes:
            if hasattr(route, "path") and hasattr(route, "methods"):
                full_path = prefix + route.path
                for method in route.methods:
                    if method != "HEAD":  # Skip HEAD methods
                        routes.append((method, full_path))
            # Handle included routers
            elif hasattr(route, "routes"):
                route_prefix = prefix
                if hasattr(route, "prefix"):
                    route_prefix = prefix + route.prefix
                collect_routes(route, route_prefix)

    # Collect from main router
    if hasattr(router, "prefix"):
        collect_routes(router, router.prefix)
    else:
        collect_routes(router, "")

    # Sort and display
    routes.sort()

    for method, path in routes:
        print(f"{method:7s} {path}")

    print()
    print(f"Total routes: {len(routes)}")
    print("=" * 80)

    # Check for chat endpoints specifically
    print("\nCHAT ENDPOINTS:")
    chat_routes = [(m, p) for m, p in routes if "/chat/" in p]
    for method, path in chat_routes:
        print(f"  {method:7s} {path}")

    if not chat_routes:
        print("  ⚠️  No chat endpoints found!")

except Exception as e:
    print(f"Error inspecting routes: {e}")
    import traceback
    traceback.print_exc()
