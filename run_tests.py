#!/usr/bin/env python3
"""
🧪 EJECUTOR DE TESTS - SISTEMA EXPLORER/GUIDED

Script para ejecutar diferentes tipos de tests del sistema Explorer/Guided
con opciones de configuración y reportes.
"""

import os
import sys
import subprocess
import argparse
import time
from datetime import datetime
from pathlib import Path


def print_banner():
    """Imprimir banner del sistema de testing"""
    print("=" * 80)
    print("🧪 SISTEMA DE TESTING - EXPLORER/GUIDED")
    print("=" * 80)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Directorio: {os.getcwd()}")
    print("=" * 80)


def check_dependencies():
    """Verificar dependencias de testing"""
    print("🔍 Verificando dependencias...")
    
    required_packages = [
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "pytest-html"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"   ✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"   ❌ {package} - FALTANTE")
    
    if missing_packages:
        print(f"\n⚠️  Paquetes faltantes: {', '.join(missing_packages)}")
        print("   Instalar con: pip install -r requirements-testing.txt")
        return False
    
    print("   ✅ Todas las dependencias están disponibles")
    return True


def create_directories():
    """Crear directorios necesarios para testing"""
    print("📁 Creando directorios de testing...")
    
    directories = [
        "reports",
        "htmlcov",
        "coverage",
        "test_results"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"   ✅ {directory}/")


def run_unit_tests(verbose=False, coverage=True):
    """Ejecutar tests unitarios"""
    print("\n🧪 EJECUTANDO TESTS UNITARIOS...")
    
    cmd = [
        "python", "-m", "pytest",
        "tests/unit/",
        "-v" if verbose else "",
        "--cov=app",
        "--cov-report=html:htmlcov",
        "--cov-report=term-missing",
        "--cov-report=xml:coverage/coverage.xml",
        "--junitxml=test_results/unit_tests.xml",
        "--html=reports/unit_tests.html",
        "--self-contained-html"
    ]
    
    cmd = [arg for arg in cmd if arg]  # Remover argumentos vacíos
    
    print(f"   Comando: {' '.join(cmd)}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    execution_time = end_time - start_time
    
    print(f"   ⏱️  Tiempo de ejecución: {execution_time:.2f}s")
    print(f"   📊 Código de salida: {result.returncode}")
    
    if result.stdout:
        print("   📤 Salida estándar:")
        print(result.stdout[-1000:])  # Últimos 1000 caracteres
    
    if result.stderr:
        print("   ⚠️  Errores:")
        print(result.stderr[-1000:])
    
    return result.returncode == 0


def run_integration_tests(verbose=False, coverage=True):
    """Ejecutar tests de integración"""
    print("\n🔗 EJECUTANDO TESTS DE INTEGRACIÓN...")
    
    cmd = [
        "python", "-m", "pytest",
        "tests/integration/",
        "-v" if verbose else "",
        "-m", "integration",
        "--cov=app",
        "--cov-report=html:htmlcov",
        "--cov-report=term-missing",
        "--junitxml=test_results/integration_tests.xml",
        "--html=reports/integration_tests.html",
        "--self-contained-html"
    ]
    
    cmd = [arg for arg in cmd if arg if arg != ""]
    
    print(f"   Comando: {' '.join(cmd)}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    execution_time = end_time - start_time
    
    print(f"   ⏱️  Tiempo de ejecución: {execution_time:.2f}s")
    print(f"   📊 Código de salida: {result.returncode}")
    
    if result.stdout:
        print("   📤 Salida estándar:")
        print(result.stdout[-1000:])
    
    if result.stderr:
        print("   ⚠️  Errores:")
        print(result.stderr[-1000:])
    
    return result.returncode == 0


def run_performance_tests(verbose=False):
    """Ejecutar tests de performance"""
    print("\n⚡ EJECUTANDO TESTS DE PERFORMANCE...")
    
    cmd = [
        "python", "-m", "pytest",
        "tests/performance/",
        "-v" if verbose else "",
        "-m", "performance",
        "--junitxml=test_results/performance_tests.xml",
        "--html=reports/performance_tests.html",
        "--self-contained-html"
    ]
    
    cmd = [arg for arg in cmd if arg if arg != ""]
    
    print(f"   Comando: {' '.join(cmd)}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    execution_time = end_time - start_time
    
    print(f"   ⏱️  Tiempo de ejecución: {execution_time:.2f}s")
    print(f"   📊 Código de salida: {result.returncode}")
    
    if result.stdout:
        print("   📤 Salida estándar:")
        print(result.stdout[-1000:])
    
    if result.stderr:
        print("   ⚠️  Errores:")
        print(result.stderr[-1000:])
    
    return result.returncode == 0


def run_e2e_tests(verbose=False):
    """Ejecutar tests end-to-end"""
    print("\n🎯 EJECUTANDO TESTS END-TO-END...")
    
    cmd = [
        "python", "-m", "pytest",
        "tests/e2e/",
        "-v" if verbose else "",
        "-m", "e2e",
        "--junitxml=test_results/e2e_tests.xml",
        "--html=reports/e2e_tests.html",
        "--self-contained-html"
    ]
    
    cmd = [arg for arg in cmd if arg if arg != ""]
    
    print(f"   Comando: {' '.join(cmd)}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    execution_time = end_time - start_time
    
    print(f"   ⏱️  Tiempo de ejecución: {execution_time:.2f}s")
    print(f"   📊 Código de salida: {result.returncode}")
    
    if result.stdout:
        print("   📤 Salida estándar:")
        print(result.stdout[-1000:])
    
    if result.stderr:
        print("   ⚠️  Errores:")
        print(result.stderr[-1000:])
    
    return result.returncode == 0


def run_all_tests(verbose=False, parallel=False, coverage=True):
    """Ejecutar todos los tests"""
    print("\n🚀 EJECUTANDO TODOS LOS TESTS...")
    
    cmd = [
        "python", "-m", "pytest",
        "tests/",
        "-v" if verbose else "",
        "--cov=app" if coverage else "",
        "--cov-report=html:htmlcov" if coverage else "",
        "--cov-report=term-missing" if coverage else "",
        "--cov-report=xml:coverage/coverage.xml" if coverage else "",
        "--junitxml=test_results/all_tests.xml",
        "--html=reports/all_tests.html",
        "--self-contained-html"
    ]
    
    cmd = [arg for arg in cmd if arg if arg != ""]
    
    print(f"   Comando: {' '.join(cmd)}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    execution_time = end_time - start_time
    
    print(f"   ⏱️  Tiempo de ejecución: {execution_time:.2f}s")
    print(f"   📊 Código de salida: {result.returncode}")
    
    if result.stdout:
        print("   📤 Salida estándar:")
        print(result.stdout[-1000:])
    
    if result.stderr:
        print("   ⚠️  Errores:")
        print(result.stderr[-1000:])
    
    return result.returncode == 0


def generate_test_report():
    """Generar reporte consolidado de tests"""
    print("\n📊 GENERANDO REPORTE CONSOLIDADO...")
    
    report_content = f"""
# 🧪 REPORTE DE TESTS - SISTEMA EXPLORER/GUIDED

## 📅 Información General
- **Fecha de ejecución**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Directorio de trabajo**: {os.getcwd()}

## 📁 Archivos de Reporte Generados

### Tests Unitarios
- **JUnit XML**: `test_results/unit_tests.xml`
- **HTML**: `reports/unit_tests.html`

### Tests de Integración
- **JUnit XML**: `test_results/integration_tests.xml`
- **HTML**: `reports/integration_tests.html`

### Tests de Performance
- **JUnit XML**: `test_results/performance_tests.xml`
- **HTML**: `reports/performance_tests.html`

### Tests End-to-End
- **JUnit XML**: `test_results/e2e_tests.xml`
- **HTML**: `reports/e2e_tests.html`

### Coverage
- **HTML**: `htmlcov/index.html`
- **XML**: `coverage/coverage.xml`

## 🎯 Próximos Pasos

1. **Revisar reportes HTML** en la carpeta `reports/`
2. **Analizar coverage** en `htmlcov/index.html`
3. **Revisar métricas de performance** en los logs
4. **Corregir fallos** identificados en los tests
5. **Optimizar servicios** basándose en métricas de performance

## 📝 Notas

- Los reportes HTML son autocontenidos y se pueden abrir en cualquier navegador
- El coverage XML puede ser integrado con herramientas CI/CD
- Los logs de JUnit pueden ser procesados por herramientas de análisis
"""
    
    report_file = "reports/TEST_REPORT.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    print(f"   ✅ Reporte generado: {report_file}")


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description="Ejecutor de tests para el sistema Explorer/Guided"
    )
    
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "performance", "e2e", "all"],
        default="all",
        help="Tipo de tests a ejecutar"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Ejecutar en modo verbose"
    )
    
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Deshabilitar reportes de coverage"
    )
    
    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="Ejecutar tests en paralelo"
    )
    
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Solo verificar dependencias"
    )
    
    args = parser.parse_args()
    
    # Imprimir banner
    print_banner()
    
    # Verificar dependencias
    if not check_dependencies():
        print("\n❌ No se pueden ejecutar los tests. Instalar dependencias primero.")
        sys.exit(1)
    
    # Si solo se quiere verificar dependencias, salir
    if args.check_deps:
        print("\n✅ Verificación de dependencias completada.")
        sys.exit(0)
    
    # Crear directorios
    create_directories()
    
    # Ejecutar tests según el tipo especificado
    success = True
    
    if args.type == "unit":
        success = run_unit_tests(args.verbose, not args.no_coverage)
    elif args.type == "integration":
        success = run_integration_tests(args.verbose, not args.no_coverage)
    elif args.type == "performance":
        success = run_performance_tests(args.verbose)
    elif args.type == "e2e":
        success = run_e2e_tests(args.verbose)
    elif args.type == "all":
        success = run_all_tests(args.verbose, args.parallel, not args.no_coverage)
    
    # Generar reporte
    generate_test_report()
    
    # Resultado final
    print("\n" + "=" * 80)
    if success:
        print("🎉 TODOS LOS TESTS COMPLETADOS EXITOSAMENTE")
        print("📊 Revisar reportes en la carpeta 'reports/'")
        print("📈 Analizar coverage en 'htmlcov/index.html'")
    else:
        print("❌ ALGUNOS TESTS FALLARON")
        print("🔍 Revisar logs y reportes para identificar problemas")
    print("=" * 80)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
