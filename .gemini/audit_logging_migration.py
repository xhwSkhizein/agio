#!/usr/bin/env python3
"""
Script to help migrate from old logger.py to new logging.py

This script finds and reports:
1. All usages of old log_ functions (log_info, log_debug, log_error, log_warning)
2. All print statements that should be replaced with logger calls
3. Provides a migration guide

Run this script to audit the codebase before doing manual replacements.
"""

import os
import re
from pathlib import Path
from collections import defaultdict

def find_old_logger_usage(directory):
    """Find all occurrences of old logger functions."""
    patterns = {
        'log_info': re.compile(r'\blog_info\s*\('),
        'log_debug': re.compile(r'\blog_debug\s*\('),
        'log_error': re.compile(r'\blog_error\s*\('),
        'log_warning': re.compile(r'\blog_warning\s*\('),
        'print': re.compile(r'\bprint\s*\('),
    }
    
    results = defaultdict(lambda: defaultdict(list))
    
    for root, dirs, files in os.walk(directory):
        # Skip certain directories
        skip_dirs = {'.venv', 'node_modules', '__pycache__', '.git', 'dist', 'build'}
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        for file in files:
            if not file.endswith('.py'):
                continue
                
            filepath = Path(root) / file
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                    for pattern_name, pattern in patterns.items():
                        for line_num, line in enumerate(lines, 1):
                            if pattern.search(line):
                                results[str(filepath)][pattern_name].append((line_num, line.strip()))
            except Exception as e:
                print(f"Error reading {filepath}: {e}")
    
    return results

def print_migration_report(results):
    """Print a migration report."""
    print("=" * 80)
    print("LOGGING MIGRATION REPORT")
    print("=" * 80)
    print()
    
    # Summary
    total_files = len(results)
    total_issues = sum(len(patterns) for patterns in results.values())
    
    print(f"Files to update: {total_files}")
    print(f"Total usages found: {sum(sum(len(occurrences) for occurrences in patterns.values()) for patterns in results.values())}")
    print()
    
    # Detailed listing
    for filepath in sorted(results.keys()):
        patterns = results[filepath]
        print(f"\n📁 {filepath}")
        print("-" * 80)
        
        for pattern_name, occurrences in patterns.items():
            if occurrences:
                print(f"\n  {pattern_name}: {len(occurrences)} occurrence(s)")
                for line_num, line in occurrences[:5]:  # Show first 5
                    print(f"    Line {line_num}: {line[:70]}")
                if len(occurrences) > 5:
                    print(f"    ... and {len(occurrences) - 5} more")
    
    print("\n" + "=" * 80)
    print("MIGRATION GUIDE")
    print("=" * 80)
    print("""
Old Pattern              → New Pattern
------------------------------------
log_info("msg")          → logger.info("event_name", key=value)
log_debug(...           → logger.debug("event_name", key=value)
log_error("msg")         → logger.error("event_name", error=str(e), exc_info=True)
print(f"text")           → logger.info("event_name", details=value)
    
Example transformations:
    log_info(f"User {user_id} logged in")
    → logger.info("user_logged_in", user_id=user_id)
    
    log_error(f"Failed to process: {e}")
    → logger.error("processing_failed", error=str(e), exc_info=True)
    
    print("✓ Started processing")
    → logger.info("processing_started")
""")

if __name__ == "__main__":
    import sys
    
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "agio"
    results = find_old_logger_usage(base_dir)
    print_migration_report(results)
