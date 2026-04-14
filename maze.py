#!/usr/bin/env python3
"""
Maze Generator & Solver
=======================
Generates random mazes using recursive backtracking and solves them
using BFS (breadth-first search). Displays the maze and solution as ASCII art.

Usage:
    python maze.py [width] [height]

Examples:
    python maze.py          # Default 15x10 maze
    python maze.py 20 15    # 20x15 maze
    python maze.py 30 20    # 30x20 maze
"""

import random
import sys
from collections import deque


def generate_maze(width, height):
    """Generate a maze using recursive backtracking (iterative with stack)."""
    # Each cell tracks which walls are open: N, S, E, W
    maze = [[0] * width for _ in range(height)]
    visited = [[False] * width for _ in range(height)]

    # Direction vectors: (dy, dx, wall_bit, opposite_wall_bit)
    N, S, E, W = 1, 2, 4, 8
    directions = [
        (-1, 0, N, S),  # North
        (1, 0, S, N),   # South
        (0, 1, E, W),   # East
        (0, -1, W, E),  # West
    ]

    stack = [(0, 0)]
    visited[0][0] = True

    while stack:
        y, x = stack[-1]
        neighbors = []
        for dy, dx, wall, opp_wall in directions:
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width and not visited[ny][nx]:
                neighbors.append((ny, nx, wall, opp_wall))

        if neighbors:
            ny, nx, wall, opp_wall = random.choice(neighbors)
            maze[y][x] |= wall
            maze[ny][nx] |= opp_wall
            visited[ny][nx] = True
            stack.append((ny, nx))
        else:
            stack.pop()

    return maze


def render_maze(maze, path=None):
    """Render the maze as ASCII art. Optionally highlight a solution path."""
    height = len(maze)
    width = len(maze[0])
    N, S, E, W = 1, 2, 4, 8

    path_set = set(path) if path else set()

    lines = []

    # Top border
    top = "+"
    for x in range(width):
        top += "---+"
    lines.append(top)

    for y in range(height):
        # Row with vertical walls
        row = "|" if not (maze[y][0] & W) else " "
        for x in range(width):
            cell = " * " if (y, x) in path_set else "   "
            if x == width - 1:
                right = "|" if not (maze[y][x] & E) else " "
            else:
                right = "|" if not (maze[y][x] & E) else " "
            row += cell + right
        lines.append(row)

        # Row with horizontal walls
        bottom = "+"
        for x in range(width):
            wall = "---" if not (maze[y][x] & S) else "   "
            bottom += wall + "+"
        lines.append(bottom)

    return "\n".join(lines)


def solve_maze(maze, start, end):
    """Solve the maze using BFS. Returns the path from start to end."""
    height = len(maze)
    width = len(maze[0])
    N, S, E, W = 1, 2, 4, 8

    directions = [
        (-1, 0, N),  # North
        (1, 0, S),   # South
        (0, 1, E),   # East
        (0, -1, W),  # West
    ]

    queue = deque([(start, [start])])
    visited = {start}

    while queue:
        (y, x), path = queue.popleft()

        if (y, x) == end:
            return path

        for dy, dx, wall in directions:
            ny, nx = y + dy, x + dx
            if (0 <= ny < height and 0 <= nx < width
                    and (ny, nx) not in visited
                    and maze[y][x] & wall):
                visited.add((ny, nx))
                queue.append(((ny, nx), path + [(ny, nx)]))

    return []


def main():
    width = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    height = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    width = max(2, min(width, 50))
    height = max(2, min(height, 30))

    print(f"\n  Maze Generator & Solver ({width}x{height})")
    print("  " + "=" * 35)

    maze = generate_maze(width, height)

    start = (0, 0)
    end = (height - 1, width - 1)

    print(f"\n  Maze (start: top-left, end: bottom-right):\n")
    print(render_maze(maze))

    path = solve_maze(maze, start, end)

    print(f"\n  Solution ({len(path)} steps, marked with *):\n")
    print(render_maze(maze, path))
    print()


if __name__ == "__main__":
    main()
