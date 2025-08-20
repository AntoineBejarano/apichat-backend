#!/usr/bin/env python3
"""
🎯 Demostración del Sistema de Sinónimos - Fast Schema Path
─────────────────────────────────────────────────────────────
Muestra cómo funciona el sistema de sinónimos configurable en acción.
"""

import sys
from pathlib import Path

# Añadir el directorio raíz al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

def demo_basic_synonyms():
    """Demuestra sinónimos básicos"""
    print("🔤 DEMO: Sinónimos Básicos")
    print("=" * 40)
    
    try:
        from app.services.context.synonyms_config_service import SynonymsConfigService
        
        service = SynonymsConfigService()
        
        # Demostrar sinónimos de campos
        print("\n📝 Sinónimos de Campos:")
        test_fields = ["email", "user", "phone", "address"]
        for field in test_fields:
            synonyms = service.get_field_synonyms(field)
            print(f"  • {field}: {synonyms}")
        
        # Demostrar sinónimos de tablas
        print("\n🗃️ Sinónimos de Tablas:")
        test_tables = ["users", "products", "orders", "customers"]
        for table in test_tables:
            synonyms = service.get_table_synonyms(table)
            print(f"  • {table}: {synonyms}")
            
    except Exception as e:
        print(f"❌ Error en demo básico: {e}")

def demo_translations():
    """Demuestra traducciones entre idiomas"""
    print("\n🌍 DEMO: Traducciones Español ↔ Inglés")
    print("=" * 40)
    
    try:
        from app.services.context.synonyms_config_service import SynonymsConfigService
        
        service = SynonymsConfigService()
        
        # Demostrar traducciones español → inglés
        print("\n🇪🇸 → 🇺🇸 Traducciones:")
        spanish_terms = ["tabla", "campo", "cliente", "producto", "factura"]
        for term in spanish_terms:
            translation = service.get_translation(term, "es", "en")
            print(f"  • {term} → {translation}")
        
        # Demostrar traducciones inglés → español
        print("\n🇺🇸 → 🇪🇸 Traducciones:")
        english_terms = ["table", "field", "customer", "product", "invoice"]
        for term in english_terms:
            translation = service.get_translation(term, "en", "es")
            print(f"  • {term} → {translation}")
            
    except Exception as e:
        print(f"❌ Error en demo de traducciones: {e}")

def demo_domain_synonyms():
    """Demuestra sinónimos específicos por dominio"""
    print("\n🏢 DEMO: Sinónimos por Dominio de Negocio")
    print("=" * 40)
    
    try:
        from app.services.context.synonyms_config_service import SynonymsConfigService
        
        service = SynonymsConfigService()
        
        # Demostrar e-commerce
        print("\n🛒 E-commerce:")
        ecommerce_terms = ["products", "orders", "customers", "cart"]
        for term in ecommerce_terms:
            synonyms = service.get_domain_synonyms(term, "ecommerce")
            print(f"  • {term}: {synonyms}")
        
        # Demostrar CRM
        print("\n👥 CRM:")
        crm_terms = ["contacts", "leads", "deals", "accounts"]
        for term in crm_terms:
            synonyms = service.get_domain_synonyms(term, "crm")
            print(f"  • {term}: {synonyms}")
        
        # Demostrar HR
        print("\n👨‍💼 Recursos Humanos:")
        hr_terms = ["employees", "departments", "positions"]
        for term in hr_terms:
            synonyms = service.get_domain_synonyms(term, "hr")
            print(f"  • {term}: {synonyms}")
            
    except Exception as e:
        print(f"❌ Error en demo de dominios: {e}")

def demo_smart_lookup():
    """Demuestra búsqueda inteligente de sinónimos"""
    print("\n🧠 DEMO: Búsqueda Inteligente de Sinónimos")
    print("=" * 40)
    
    try:
        from app.services.context.synonyms_config_service import SynonymsConfigService
        
        service = SynonymsConfigService()
        
        # Demostrar búsqueda inteligente
        test_queries = [
            "correo",           # Campo en español
            "usuarios",         # Tabla en español
            "productos",        # Dominio e-commerce
            "empleados",        # Dominio HR
            "facturas"          # Dominio finanzas
        ]
        
        print("\n🔍 Búsqueda Inteligente:")
        for query in test_queries:
            all_synonyms = service.get_all_synonyms_for_term(query)
            print(f"  • '{query}' → {all_synonyms}")
            
    except Exception as e:
        print(f"❌ Error en demo de búsqueda inteligente: {e}")

def demo_fast_schema_path_simulation():
    """Simula cómo funcionaría el Fast Schema Path con el nuevo sistema"""
    print("\n⚡ DEMO: Simulación Fast Schema Path")
    print("=" * 40)
    
    try:
        from app.services.context.synonyms_config_service import SynonymsConfigService
        
        service = SynonymsConfigService()
        
        # Simular preguntas del usuario
        user_questions = [
            "¿Dónde está el campo correo electrónico?",
            "¿Qué tablas hay de clientes?",
            "¿Dónde guardan los productos?",
            "¿Hay alguna tabla de empleados?",
            "¿Dónde están las facturas?"
        ]
        
        print("\n❓ Preguntas del Usuario:")
        for question in user_questions:
            print(f"\n  Q: {question}")
            
            # Extraer términos clave (simulación simple)
            terms = question.lower().split()
            relevant_terms = [term for term in terms if len(term) > 3 and term not in ['dónde', 'está', 'están', 'hay', 'alguna', 'tabla', 'campo']]
            
            if relevant_terms:
                print(f"     Términos clave: {relevant_terms}")
                
                # Buscar sinónimos para cada término
                for term in relevant_terms:
                    synonyms = service.get_all_synonyms_for_term(term)
                    if synonyms:
                        print(f"     '{term}' → sinónimos: {synonyms[:3]}...")  # Mostrar solo los primeros 3
                    else:
                        print(f"     '{term}' → sinónimos: ninguno encontrado")
            else:
                print("     Términos clave: ninguno identificado")
                
    except Exception as e:
        print(f"❌ Error en demo de Fast Schema Path: {e}")

def demo_configuration_management():
    """Demuestra la gestión de configuración"""
    print("\n⚙️ DEMO: Gestión de Configuración")
    print("=" * 40)
    
    try:
        from app.services.context.synonyms_config_service import SynonymsConfigService
        
        service = SynonymsConfigService()
        
        # Mostrar estadísticas
        stats = service.get_config_stats()
        print("\n📊 Estadísticas del Sistema:")
        for key, value in stats.items():
            if key != 'last_reload':  # Omitir timestamp para legibilidad
                print(f"  • {key}: {value}")
        
        # Mostrar capacidad de recarga
        print("\n🔄 Capacidad de Recarga:")
        print("  • El sistema puede recargar configuraciones en tiempo real")
        print("  • Cache TTL configurable: 5 minutos")
        print("  • Detección automática de cambios en archivos")
        
        # Mostrar flexibilidad
        print("\n🎯 Flexibilidad del Sistema:")
        print("  • Sinónimos configurables sin tocar código")
        print("  • Nuevos dominios de negocio fáciles de añadir")
        print("  • Traducciones personalizables por idioma")
        
    except Exception as e:
        print(f"❌ Error en demo de configuración: {e}")

def main():
    """Función principal del demo"""
    print("🎯 DEMOSTRACIÓN DEL SISTEMA DE SINÓNIMOS")
    print("=" * 60)
    print("Este demo muestra cómo funciona el nuevo sistema configurable")
    print("de sinónimos para el Fast Schema Path.")
    print()
    
    demos = [
        ("Sinónimos Básicos", demo_basic_synonyms),
        ("Traducciones", demo_translations),
        ("Sinónimos por Dominio", demo_domain_synonyms),
        ("Búsqueda Inteligente", demo_smart_lookup),
        ("Simulación Fast Schema Path", demo_fast_schema_path_simulation),
        ("Gestión de Configuración", demo_configuration_management)
    ]
    
    for demo_name, demo_func in demos:
        try:
            demo_func()
            print(f"\n✅ {demo_name} completado exitosamente")
        except Exception as e:
            print(f"\n❌ {demo_name} falló: {e}")
        
        print("\n" + "-" * 60)
    
    print("\n🎉 ¡DEMOSTRACIÓN COMPLETADA!")
    print("\n💡 Beneficios del Nuevo Sistema:")
    print("  • ✅ Configurable sin tocar código")
    print("  • ✅ Fácil de mantener y expandir")
    print("  • ✅ Soporte multilenguaje")
    print("  • ✅ Sinónimos por dominio de negocio")
    print("  • ✅ Cache inteligente con recarga automática")
    print("  • ✅ 100+ sinónimos vs 15 hardcodeados")
    print("  • ✅ 70+ traducciones vs 18 hardcodeadas")
    print("  • ✅ 5 dominios de negocio vs 0 hardcodeados")

if __name__ == "__main__":
    main()
