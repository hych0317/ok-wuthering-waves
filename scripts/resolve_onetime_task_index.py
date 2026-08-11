import ast
import sys
from pathlib import Path


def resolve_onetime_task_index(config_path, class_name):
    tree = ast.parse(Path(config_path).read_text(encoding='utf-8'))
    config_node = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'config' for target in node.targets)
    )
    tasks_node = next(
        value
        for key, value in zip(config_node.keys, config_node.values)
        if isinstance(key, ast.Constant) and key.value == 'onetime_tasks'
    )
    for index, task_node in enumerate(tasks_node.elts, start=1):
        task = ast.literal_eval(task_node)
        if len(task) >= 2 and task[1] == class_name:
            return index
    return 0


def main():
    if len(sys.argv) != 2:
        print('usage: resolve_onetime_task_index.py CLASS_NAME', file=sys.stderr)
        return 2
    try:
        print(resolve_onetime_task_index('config.py', sys.argv[1]))
    except (OSError, SyntaxError, StopIteration, ValueError) as error:
        print(f'failed to parse config.py: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
