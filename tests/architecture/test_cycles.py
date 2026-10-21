"""Architecture checks for import cycles."""

from tests.architecture._imports import package_import_graph


def _find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    visited: set[str] = set()
    active: set[str] = set()
    stack: list[str] = []

    def visit(module: str) -> list[str] | None:
        if module in active:
            index = stack.index(module)
            return [*stack[index:], module]

        if module in visited:
            return None

        visited.add(module)
        active.add(module)
        stack.append(module)

        for dependency in sorted(graph[module]):
            cycle = visit(dependency)

            if cycle is not None:
                return cycle

        stack.pop()
        active.remove(module)
        return None

    for module in sorted(graph):
        cycle = visit(module)

        if cycle is not None:
            return cycle

    return None


def test_ff_004_package_import_graph_has_no_cycles() -> None:
    graph = package_import_graph()
    cycle = _find_cycle(graph)

    assert cycle is None, "Import cycle found: " + " -> ".join(cycle or [])
