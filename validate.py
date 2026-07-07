#!/usr/bin/env python
"""Script de validación rápida para calidad de código.

Ejecuta todas las herramientas de validación de una vez:
- Black (formateador)
- Flake8 (linter)
- Pydocstyle (validador de docstrings)
- Pytest (tests)

Uso: python validate.py [--fix]
"""

import subprocess
import sys
from pathlib import Path

PACKAGES = ["cards", "alerts", "tasks", "users", "config", "tests"]
PROJECT_ROOT = Path(__file__).parent

def run_command(cmd, description, fix=False):
    """Ejecuta un comando y reporta resultados."""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=False, text=True)
        if result.returncode == 0:
            print(f"✓ {description} - PASSED")
            return True
        else:
            print(f"✗ {description} - FAILED (exit code: {result.returncode})")
            if fix:
                print(f"  Intenta corregir automáticamente ejecutando: {' '.join(cmd[:3])}")
            return False
    except Exception as e:
        print(f"✗ Error ejecutando {description}: {e}")
        return False

def main():
    fix = "--fix" in sys.argv
    results = {}
    
    # 1. Black (formateador)
    if fix:
        print("\n[FIX MODE] Ejecutando Black para formatear...")
        cmd = ["python", "-m", "black"] + PACKAGES + ["--line-length", "100"]
        run_command(cmd, "Black (formateador)", fix=True)
    
    # 2. Flake8 (linter)
    cmd = ["python", "-m", "flake8"] + PACKAGES
    results["flake8"] = run_command(cmd, "Flake8 (linter)")
    
    # 3. Pydocstyle (docstrings)
    cmd = ["python", "-m", "pydocstyle", "--convention=google"] + PACKAGES
    results["pydocstyle"] = run_command(cmd, "Pydocstyle (docstrings)")
    
    # 4. Pytest (tests)
    cmd = ["python", "-m", "pytest", "tests/", "-v"]
    results["pytest"] = run_command(cmd, "Pytest (tests)")
    
    # Resumen
    print(f"\n{'='*60}")
    print("  RESUMEN DE VALIDACIÓN")
    print(f"{'='*60}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for tool, success in results.items():
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"  {tool:20} {status}")
    
    print(f"\n  Resultado: {passed}/{total} validaciones pasadas")
    print(f"{'='*60}\n")
    
    if passed == total:
        print("✓ ¡Código listo para commit!")
        return 0
    else:
        print("✗ Por favor, corrige los errores reportados arriba.")
        if not fix:
            print("  Tip: ejecuta 'python validate.py --fix' para corregir automáticamente.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
