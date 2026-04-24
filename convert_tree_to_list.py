import os
import re
import sys

def migrate_xml_files(target_path):
    # Regex explicada:
    # (?<!id=")(?<!name=")  -> Lookbehind negativo: No debe estar precedido por id=" o name="
    # \btree\b              -> La palabra exacta 'tree' con límites de palabra
    pattern = r'(?<!id=")(?<!name=")\btree\b'
    replacement = 'list'

    # Verificamos si la ruta existe
    if not os.path.exists(target_path):
        print(f"❌ Error: La ruta '{target_path}' no existe.")
        return

    count_files = 0
    count_changes = 0

    print(f"🔍 Buscando archivos .xml en: {target_path}...")

    for root, _, files in os.walk(target_path):
        for file in files:
            if file.endswith(".xml"):
                file_path = os.path.join(root, file)
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Realizamos el reemplazo
                new_content = re.sub(pattern, replacement, content)

                if new_content != content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"✅ Modificado: {file_path}")
                    count_changes += 1
                
                count_files += 1

    print(f"\n🚀 Finalizado.")
    print(f"📂 Archivos analizados: {count_files}")
    print(f"📝 Archivos modificados: {count_changes}")

if __name__ == "__main__":
    # Verificamos si se pasó el argumento de la ruta
    if len(sys.argv) < 2:
        print("Uso: python3 migrate_views.py <ruta_de_la_carpeta>")
        print("Ejemplo: python3 migrate_views.py ./addons/modulo/views")
    else:
        ruta = sys.argv[1]
        migrate_xml_files(ruta)