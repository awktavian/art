import ast
import os
import networkx as nx
from collections import defaultdict

# Configuration
ROOT_DIR = os.path.abspath("kagami")
IGNORE_DIRS = {"__pycache__", "tests", "mocks", "migrations"}


def get_module_name(file_path):
    rel_path = os.path.relpath(file_path, os.path.dirname(ROOT_DIR))
    return rel_path.replace("/", ".").replace(".py", "")


def analyze_imports(root_dir):
    graph = nx.DiGraph()
    file_map = {}  # path -> module_name
    module_map = {}  # module_name -> path

    # 1. Discovery
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                module_name = get_module_name(full_path)
                file_map[full_path] = module_name
                module_map[module_name] = full_path
                graph.add_node(module_name, type="module", path=full_path)

    # 2. Parsing
    for full_path, module_name in file_map.items():
        try:
            with open(full_path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=full_path)
        except Exception as e:
            print(f"Error parsing {full_path}: {e}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name
                    if target.startswith("kagami."):
                        graph.add_edge(module_name, target)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("kagami."):
                    graph.add_edge(module_name, node.module)
                elif node.level > 0:
                    # Handle relative imports (simplified)
                    # This is tricky without full resolution logic, skipping for now or could approximate
                    pass

    return graph, module_map


def check_duplicates(file_map):
    # Check for similar filenames
    names = defaultdict(list)
    for path in file_map.values():
        basename = os.path.basename(path)
        names[basename].append(path)

    duplicates = {k: v for k, v in names.items() if len(v) > 1}
    return duplicates


def analyze_topology():
    print(f"Analyzing topology of {ROOT_DIR}...")
    graph, _module_map = analyze_imports(ROOT_DIR)

    # 1. Cycles
    try:
        cycles = list(nx.simple_cycles(graph))
        print(f"\nFound {len(cycles)} circular dependency cycles.")
        if cycles:
            # Sort by length
            cycles.sort(key=len)
            print("Shortest 5 cycles:")
            for c in cycles[:5]:
                print(f"  - {' -> '.join(c)}")
    except Exception as e:
        print(f"Could not detect cycles (graph too large?): {e}")

    # 2. Octonion/Fano Duplication Checks
    print("\nChecking for Octonion/Fano duplications...")
    relevant_modules = [n for n in graph.nodes if "octonion" in n or "fano" in n]
    for m in sorted(relevant_modules):
        print(f"  - {m}")

    # 3. Inference Flow (Heuristic)
    print("\nTracing 'inference' flow...")
    inference_nodes = [n for n in graph.nodes if "inference" in n]
    if inference_nodes:
        print(f"  Found {len(inference_nodes)} inference-related modules.")
        # Check centrality
        degree = dict(graph.degree(inference_nodes))
        top_inf = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:5]
        print("  Top connected inference modules:")
        for m, d in top_inf:
            print(f"    {m} (degree {d})")

    # 4. Orphaned Modules (in kagami.core)
    # Modules with in-degree 0 (except __init__)
    print("\nChecking for potentially orphaned modules (In-Degree 0)...")
    orphans = []
    for n in graph.nodes:
        if graph.in_degree(n) == 0 and not n.endswith("__init__"):
            # Filter strictly for core
            if "kagami.core" in n:
                orphans.append(n)

    print(f"  Found {len(orphans)} potential orphans (no internal imports detected):")
    for o in sorted(orphans)[:10]:  # Show first 10
        print(f"    {o}")


if __name__ == "__main__":
    analyze_topology()
