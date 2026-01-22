#!/usr/bin/env python3
"""Performance benchmark script for diacea.

Generate test data and run benchmarks. Can be used with hyperfine:

    # Generate test data first
    python scripts/benchmark.py --generate

    # Then benchmark with hyperfine
    hyperfine --warmup 3 \
        'python -m diacea.cli -i /tmp/diacea_bench/small.json -f mermaid -o /dev/null' \
        'python -m diacea.cli -i /tmp/diacea_bench/medium.json -f mermaid -o /dev/null' \
        'python -m diacea.cli -i /tmp/diacea_bench/large.json -f mermaid -o /dev/null'

    # Or run the built-in benchmark
    python scripts/benchmark.py --run

    # Run with memory tracking
    python scripts/benchmark.py --run --memory
"""

from __future__ import annotations

import argparse
import gc
import json
import random
import string
import sys
import time
import tracemalloc
from pathlib import Path

BENCH_DIR = Path('/tmp/diacea_bench')


def generate_id() -> str:
    return ''.join(random.choices(string.ascii_lowercase, k=8))


def generate_excalidraw_diagram(num_shapes: int, num_connections: int) -> dict:
    """Generate an Excalidraw-format diagram with specified complexity."""
    elements = []

    shapes = []
    for i in range(num_shapes):
        shape_id = f'shape_{i}'
        x = (i % 10) * 150.0
        y = (i // 10) * 100.0

        shape_type = random.choice(['rectangle', 'ellipse', 'diamond'])
        element = {
            'id': shape_id,
            'type': shape_type,
            'x': x,
            'y': y,
            'width': 100.0 + random.uniform(-20, 20),
            'height': 60.0 + random.uniform(-10, 10),
            'strokeColor': '#000000',
            'backgroundColor': random.choice(['transparent', '#e3f2fd', '#fff3e0', '#e8f5e9']),
            'strokeWidth': 2,
            'roughness': 1,
            'seed': random.randint(1, 1000000),
        }
        elements.append(element)
        shapes.append(shape_id)

        if random.random() < 0.7:
            text_element = {
                'id': f'text_{i}',
                'type': 'text',
                'x': x + 10,
                'y': y + 20,
                'width': 80.0,
                'height': 20.0,
                'text': f'Shape {i}',
                'fontSize': 14,
                'fontFamily': 1,
            }
            elements.append(text_element)

    for i in range(min(num_connections, len(shapes) - 1)):
        from_idx = random.randint(0, len(shapes) - 1)
        to_idx = random.randint(0, len(shapes) - 1)
        if from_idx == to_idx:
            to_idx = (to_idx + 1) % len(shapes)

        from_id = shapes[from_idx]
        to_id = shapes[to_idx]

        arrow = {
            'id': f'arrow_{i}',
            'type': 'arrow',
            'x': 0.0,
            'y': 0.0,
            'points': [[0.0, 0.0], [100.0, 50.0]],
            'startBinding': {'elementId': from_id},
            'endBinding': {'elementId': to_id},
            'strokeColor': '#000000',
            'strokeWidth': 2,
        }
        elements.append(arrow)

    return {'elements': elements, 'type': 'excalidraw'}


def generate_test_data() -> None:
    """Generate test data files for benchmarking."""
    BENCH_DIR.mkdir(parents=True, exist_ok=True)

    configs = [
        ('tiny', 10, 5),
        ('small', 50, 30),
        ('medium', 200, 150),
        ('large', 500, 400),
        ('xlarge', 1000, 800),
        ('xxlarge', 2000, 1500),
    ]

    for name, shapes, connections in configs:
        diagram = generate_excalidraw_diagram(shapes, connections)
        output_path = BENCH_DIR / f'{name}.json'
        output_path.write_text(json.dumps(diagram, indent=2))
        print(f'Generated {output_path} ({shapes} shapes, {connections} connections)')


def run_benchmark(track_memory: bool = False) -> None:
    """Run internal benchmarks and report results."""
    from diacea.generators import (
        C4PlantUMLGenerator,
        D2Generator,
        GraphVizGenerator,
        MermaidGenerator,
        PlantUMLGenerator,
    )
    from diacea.parsers import ExcalidrawParser

    if not BENCH_DIR.exists():
        print('Generating test data...')
        generate_test_data()

    parser = ExcalidrawParser()
    generators = {
        'plantuml': PlantUMLGenerator(),
        'c4': C4PlantUMLGenerator(),
        'mermaid': MermaidGenerator(),
        'graphviz': GraphVizGenerator(),
        'd2': D2Generator(),
    }

    results: dict[str, dict[str, list[float]]] = {}
    memory_results: dict[str, dict[str, int]] = {}
    output_sizes: dict[str, dict[str, int]] = {}

    for data_file in sorted(BENCH_DIR.glob('*.json')):
        size_name = data_file.stem
        results[size_name] = {}
        memory_results[size_name] = {}
        output_sizes[size_name] = {}

        with open(data_file) as f:
            data = json.load(f)

        parse_times = []
        for _ in range(5):
            gc.collect()
            start = time.perf_counter()
            diagram = parser.parse(data)
            parse_times.append(time.perf_counter() - start)
        results[size_name]['parse'] = parse_times

        if track_memory:
            gc.collect()
            tracemalloc.start()
            diagram = parser.parse(data)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            memory_results[size_name]['parse'] = peak

        diagram = parser.parse(data)

        for gen_name, generator in generators.items():
            gen_times = []
            output = ''
            for _ in range(5):
                gc.collect()
                start = time.perf_counter()
                output = generator.generate(diagram)
                gen_times.append(time.perf_counter() - start)
            results[size_name][gen_name] = gen_times
            output_sizes[size_name][gen_name] = len(output)

            if track_memory:
                gc.collect()
                tracemalloc.start()
                generator.generate(diagram)
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                memory_results[size_name][gen_name] = peak

    print('\n' + '=' * 85)
    print('BENCHMARK RESULTS (5 iterations each, times in ms)')
    print('=' * 85)

    header = f"{'Size':<10} {'Parse':<12}"
    for gen_name in generators:
        header += f'{gen_name:<12}'
    print(header)
    print('-' * 85)

    for size_name, timings in results.items():
        row = f'{size_name:<10}'
        parse_avg = sum(timings['parse']) / len(timings['parse']) * 1000
        row += f'{parse_avg:>8.2f} ms '

        for gen_name in generators:
            gen_avg = sum(timings[gen_name]) / len(timings[gen_name]) * 1000
            row += f'{gen_avg:>8.2f} ms '

        print(row)

    if track_memory:
        print('\n' + '=' * 85)
        print('MEMORY USAGE (peak bytes)')
        print('=' * 85)

        header = f"{'Size':<10} {'Parse':<12}"
        for gen_name in generators:
            header += f'{gen_name:<12}'
        print(header)
        print('-' * 85)

        for size_name, mem in memory_results.items():
            row = f'{size_name:<10}'
            row += f'{_format_bytes(mem.get("parse", 0)):>10} '

            for gen_name in generators:
                row += f'{_format_bytes(mem.get(gen_name, 0)):>10} '

            print(row)

    print('\n' + '=' * 85)
    print('OUTPUT SIZES (bytes)')
    print('=' * 85)

    header = f"{'Size':<10} "
    for gen_name in generators:
        header += f'{gen_name:<12}'
    print(header)
    print('-' * 85)

    for size_name, sizes in output_sizes.items():
        row = f'{size_name:<10} '
        for gen_name in generators:
            row += f'{_format_bytes(sizes.get(gen_name, 0)):>10} '
        print(row)

    print('=' * 85)
    print(f'\nTest data location: {BENCH_DIR}')
    print('\nTo benchmark with hyperfine:')
    print('  hyperfine --warmup 3 \\')
    print(f"    'python -m diacea.cli -i {BENCH_DIR}/small.json -f mermaid -o -' \\")
    print(f"    'python -m diacea.cli -i {BENCH_DIR}/medium.json -f mermaid -o -' \\")
    print(f"    'python -m diacea.cli -i {BENCH_DIR}/large.json -f mermaid -o -'")


def _format_bytes(num_bytes: int) -> str:
    """Format bytes in human-readable form."""
    if num_bytes < 1024:
        return f'{num_bytes}B'
    elif num_bytes < 1024 * 1024:
        return f'{num_bytes / 1024:.1f}KB'
    else:
        return f'{num_bytes / (1024 * 1024):.1f}MB'


def main() -> int:
    arg_parser = argparse.ArgumentParser(description='Diacea performance benchmarks')
    arg_parser.add_argument(
        '--generate',
        action='store_true',
        help='Generate test data files',
    )
    arg_parser.add_argument(
        '--run',
        action='store_true',
        help='Run benchmarks',
    )
    arg_parser.add_argument(
        '--memory',
        action='store_true',
        help='Track memory usage (slower)',
    )
    arg_parser.add_argument(
        '--clean',
        action='store_true',
        help='Clean up test data',
    )

    args = arg_parser.parse_args()

    if args.clean:
        import shutil
        if BENCH_DIR.exists():
            shutil.rmtree(BENCH_DIR)
            print(f'Cleaned up {BENCH_DIR}')
        return 0

    if args.generate:
        generate_test_data()
        return 0

    if args.run:
        run_benchmark(track_memory=args.memory)
        return 0

    arg_parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
