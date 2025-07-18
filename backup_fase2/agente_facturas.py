import sqlite3
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from openai import OpenAI
import re
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logger = logging.getLogger(__name__)

class AgenteFacturas:
    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
        self.db.row_factory = sqlite3.Row

    def procesar_consulta(self, consulta_usuario: str) -> Dict:
        """
        Procesa una consulta en lenguaje natural y devuelve resultados
        """
        try:
            # 1. Analizar la consulta con OpenAI
            sql_query = self._generar_sql_desde_consulta(consulta_usuario)

            # 2. Ejecutar la consulta SQL
            resultados = self._ejecutar_consulta_sql(sql_query)

            # 3. Generar respuesta en lenguaje natural
            respuesta = self._generar_respuesta_natural(consulta_usuario, resultados)

            return {
                "consulta_original": consulta_usuario,
                "sql_generado": sql_query,
                "resultados": resultados,
                "respuesta": respuesta,
                "exito": True
            }

        except Exception as e:
            logger.error(f"Error procesando consulta: {e}")
            return {
                "consulta_original": consulta_usuario,
                "error": str(e),
                "exito": False
            }

    def _generar_sql_desde_consulta(self, consulta: str) -> str:
        """
        Usa OpenAI para convertir lenguaje natural a SQL
        """
        prompt = f"""
        Eres un experto en SQL que trabaja con una base de datos de facturas argentinas.
        
        ESQUEMA DE LA BASE DE DATOS:
        Tabla: facturas
        Columnas:
        - id (INTEGER PRIMARY KEY)
        - filename (TEXT) - nombre del archivo
        - razon_social (TEXT) - nombre del proveedor
        - cuit_proveedor (TEXT) - CUIT del proveedor (formato: XX-XXXXXXXX-X)
        - subtotal (REAL) - monto sin IVA
        - iva (REAL) - monto del IVA
        - total (REAL) - monto total
        - created_at (TIMESTAMP) - fecha de procesamiento
        
        CONSULTA DEL USUARIO: "{consulta}"
        
        INSTRUCCIONES IMPORTANTES:
        1. Genera SOLO consultas SELECT, nunca CREATE, DROP, INSERT, UPDATE, DELETE
        2. Usa SQLite syntax
        3. Para fechas usa strftime y DATE()
        4. Para búsquedas de texto usa LIKE con %
        5. Limita resultados a 50 con LIMIT
        6. Ordena por fecha más reciente (ORDER BY created_at DESC)
        7. NUNCA uses palabras como CREATE, DROP, DELETE, UPDATE, INSERT, ALTER
        
        EJEMPLOS VÁLIDOS:
        - "facturas de enero" -> SELECT * FROM facturas WHERE strftime('%m', created_at) = '01' ORDER BY created_at DESC LIMIT 50
        - "facturas mayores a 100000" -> SELECT * FROM facturas WHERE total > 100000 ORDER BY created_at DESC LIMIT 50
        - "facturas de mercado libre" -> SELECT * FROM facturas WHERE razon_social LIKE '%mercado%libre%' ORDER BY created_at DESC LIMIT 50
        - "total de facturas" -> SELECT COUNT(*) as total_facturas FROM facturas
        - "facturas sin CUIT" -> SELECT * FROM facturas WHERE cuit_proveedor IS NULL OR cuit_proveedor = '' ORDER BY created_at DESC LIMIT 50
        
        RESPONDE SOLO CON EL SQL:
        """

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1
            )

            sql_query = response.choices[0].message.content.strip()

            # Limpiar la respuesta
            sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
            
            # Asegurar que empiece con SELECT
            if not sql_query.upper().startswith('SELECT'):
                logger.warning(f"Consulta no válida generada: {sql_query}")
                return "SELECT * FROM facturas ORDER BY created_at DESC LIMIT 10"

            logger.info(f"SQL generado: {sql_query}")
            return sql_query

        except Exception as e:
            logger.error(f"Error generando SQL: {e}")
            # Consulta por defecto
            return "SELECT * FROM facturas ORDER BY created_at DESC LIMIT 10"

    def _ejecutar_consulta_sql(self, sql_query: str) -> List[Dict]:
        """
        Ejecuta la consulta SQL de forma segura - VERSIÓN MEJORADA
        """
        try:
            # Validaciones de seguridad mejoradas
            sql_upper = sql_query.upper().strip()
            
            # Lista ampliada de operaciones prohibidas
            operaciones_prohibidas = [
                'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 
                'CREATE', 'TRUNCATE', 'REPLACE', 'EXEC', 'EXECUTE',
                'CALL', 'PRAGMA', 'ATTACH', 'DETACH'
            ]
            
            # Verificar que sea una consulta SELECT
            if not sql_upper.startswith('SELECT'):
                raise ValueError("Solo se permiten consultas SELECT")
            
            # Buscar palabras prohibidas como palabras completas
            for operacion in operaciones_prohibidas:
                # Usar regex para buscar la palabra completa
                patron = r'\b' + re.escape(operacion) + r'\b'
                if re.search(patron, sql_upper):
                    raise ValueError(f"Operación no permitida: {operacion}")
            
            # Verificar que no contenga múltiples statements
            if ';' in sql_query.rstrip(';'):
                raise ValueError("No se permiten múltiples declaraciones SQL")

            # Limitar complejidad de consulta
            if len(sql_query) > 1000:
                raise ValueError("Consulta demasiado compleja")

            cursor = self.db.cursor()
            
            # Configurar timeout de consulta
            cursor.execute("PRAGMA query_timeout = 30000")  # 30 segundos
            cursor.execute(sql_query)

            # Limitar número de resultados para evitar sobrecarga
            resultados_raw = cursor.fetchmany(100)  # Máximo 100 resultados
            
            resultados = []
            for row in resultados_raw:
                # Convertir sqlite3.Row a diccionario
                resultado = dict(row)

                # Formatear datos para mejor presentación
                if resultado.get('total'):
                    try:
                        total_num = float(resultado['total'])
                        resultado['total_formateado'] = f"${total_num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    except (ValueError, TypeError):
                        resultado['total_formateado'] = str(resultado['total'])

                if resultado.get('cuit_proveedor'):
                    cuit = resultado['cuit_proveedor']
                    if len(cuit) == 11 and cuit.isdigit():
                        resultado['cuit_formateado'] = f"{cuit[:2]}-{cuit[2:10]}-{cuit[10]}"
                    else:
                        resultado['cuit_formateado'] = cuit

                if resultado.get('created_at'):
                    # Formatear fecha
                    fecha = resultado['created_at'][:10]
                    resultado['fecha_formateada'] = fecha

                resultados.append(resultado)

            return resultados

        except sqlite3.Error as e:
            logger.error(f"Error SQL ejecutando consulta: {e}")
            raise ValueError(f"Error en consulta SQL: {str(e)}")
        except Exception as e:
            logger.error(f"Error ejecutando SQL: {e}")
            raise

    def _generar_respuesta_natural(self, consulta_original: str, resultados: List[Dict]) -> str:
        """
        Genera una respuesta en lenguaje natural basada en los resultados
        """
        try:
            if not resultados:
                return "No se encontraron facturas que coincidan con tu consulta."

            # Preparar resumen de resultados
            total_facturas = len(resultados)
            
            # Calcular suma total solo si hay columna 'total'
            suma_total = 0
            for r in resultados:
                if r.get('total'):
                    try:
                        total_valor = r.get('total')
                        if isinstance(total_valor, (int, float)):
                            suma_total += float(total_valor)
                        elif isinstance(total_valor, str):
                            # Limpiar formato argentino si viene como string
                            total_limpio = total_valor.replace('$', '').replace(' ', '').replace('.', '').replace(',', '.')
                            suma_total += float(total_limpio)
                    except (ValueError, TypeError):
                        pass

            # Obtener algunos ejemplos
            ejemplos = []
            for i, resultado in enumerate(resultados[:3]):
                if 'razon_social' in resultado:
                    razon_social = resultado.get('razon_social', 'Sin nombre')
                    total = resultado.get('total_formateado', 'N/A')
                    fecha = resultado.get('fecha_formateada', 'N/A')
                    ejemplos.append(f"• {razon_social} - {total} ({fecha})")
                else:
                    # Para consultas de agregación (COUNT, SUM, etc.)
                    ejemplos.append(f"• {resultado}")

            prompt = f"""
            Genera una respuesta natural y útil basada en estos datos:
            
            CONSULTA ORIGINAL: "{consulta_original}"
            RESULTADOS ENCONTRADOS: {total_facturas} registros
            SUMA TOTAL: ${suma_total}
            
            EJEMPLOS:
            {chr(10).join(ejemplos)}
            
            INSTRUCCIONES:
            1. Responde en español de forma natural y amigable
            2. Menciona la cantidad de resultados encontrados
            3. Si hay suma total significativa, menciónala
            4. Da ejemplos específicos si los hay
            5. Mantén la respuesta concisa pero informativa
            6. Usa un tono profesional pero cercano
            7. Si son resultados de agregación (COUNT, SUM), explica el resultado
            
            RESPUESTA:
            """

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generando respuesta natural: {e}")
            return f"Encontré {len(resultados)} resultados que coinciden con tu consulta."

    def buscar_facturas_similares(self, factura_id: int) -> List[Dict]:
        """
        Encuentra facturas similares a una dada
        """
        try:
            cursor = self.db.cursor()

            # Obtener la factura de referencia
            cursor.execute("SELECT * FROM facturas WHERE id = ?", (factura_id,))
            factura_ref = cursor.fetchone()

            if not factura_ref:
                return []

            # Buscar facturas similares
            similares = []

            # 1. Mismo proveedor
            if factura_ref['razon_social']:
                cursor.execute("""
                    SELECT *, 'Mismo proveedor' as motivo_similitud
                    FROM facturas 
                    WHERE razon_social = ? AND id != ?
                    ORDER BY created_at DESC LIMIT 5
                """, (factura_ref['razon_social'], factura_id))
                similares.extend([dict(row) for row in cursor.fetchall()])

            # 2. Mismo CUIT
            if factura_ref['cuit_proveedor']:
                cursor.execute("""
                    SELECT *, 'Mismo CUIT' as motivo_similitud
                    FROM facturas 
                    WHERE cuit_proveedor = ? AND id != ?
                    ORDER BY created_at DESC LIMIT 5
                """, (factura_ref['cuit_proveedor'], factura_id))
                similares.extend([dict(row) for row in cursor.fetchall()])

            # 3. Monto similar (±20%)
            if factura_ref['total']:
                margen = factura_ref['total'] * 0.2
                cursor.execute("""
                    SELECT *, 'Monto similar' as motivo_similitud
                    FROM facturas 
                    WHERE total BETWEEN ? AND ? AND id != ?
                    ORDER BY created_at DESC LIMIT 5
                """, (factura_ref['total'] - margen, factura_ref['total'] + margen, factura_id))
                similares.extend([dict(row) for row in cursor.fetchall()])

            # Eliminar duplicados y formatear
            facturas_unicas = {}
            for factura in similares:
                if factura['id'] not in facturas_unicas:
                    facturas_unicas[factura['id']] = factura

            return list(facturas_unicas.values())[:10]  # Limitar a 10 resultados

        except Exception as e:
            logger.error(f"Error buscando facturas similares: {e}")
            return []

    def detectar_duplicados(self) -> List[Dict]:
        """
        Detecta posibles facturas duplicadas
        """
        try:
            cursor = self.db.cursor()

            # Buscar por CUIT + monto + fecha similar
            cursor.execute("""
                SELECT 
                    f1.id as id1, f1.filename as filename1, f1.razon_social as razon_social1,
                    f2.id as id2, f2.filename as filename2, f2.razon_social as razon_social2,
                    f1.total, f1.cuit_proveedor,
                    DATE(f1.created_at) as fecha1, DATE(f2.created_at) as fecha2
                FROM facturas f1
                JOIN facturas f2 ON f1.id < f2.id
                WHERE f1.cuit_proveedor = f2.cuit_proveedor
                AND f1.total = f2.total
                AND DATE(f1.created_at) = DATE(f2.created_at)
                ORDER BY f1.created_at DESC
            """)

            duplicados = []
            for row in cursor.fetchall():
                duplicado = dict(row)
                duplicado['motivo'] = 'Mismo CUIT, monto y fecha'
                duplicado['total_formateado'] = f"${duplicado['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                duplicados.append(duplicado)

            return duplicados

        except Exception as e:
            logger.error(f"Error detectando duplicados: {e}")
            return []

    def obtener_estadisticas_inteligentes(self) -> Dict:
        """
        Genera estadísticas inteligentes sobre las facturas - VERSIÓN CONSOLIDADA Y OPTIMIZADA
        """
        try:
            cursor = self.db.cursor()

            # Estadísticas básicas con consultas optimizadas
            stats = {}

            # Total facturas
            cursor.execute("SELECT COUNT(*) as total FROM facturas")
            stats['total_facturas'] = cursor.fetchone()[0]

            # Suma total con manejo de NULL
            cursor.execute("""
                SELECT COALESCE(SUM(total), 0) as suma_total 
                FROM facturas 
                WHERE total IS NOT NULL
            """)
            suma_total = cursor.fetchone()[0]
            stats['suma_total'] = suma_total
            stats['suma_total_formateada'] = f"${suma_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            # Top 5 proveedores optimizado
            cursor.execute("""
                SELECT 
                    razon_social, 
                    COUNT(*) as cantidad, 
                    COALESCE(SUM(total), 0) as total_proveedor
                FROM facturas 
                WHERE razon_social IS NOT NULL AND razon_social != ''
                GROUP BY razon_social
                ORDER BY total_proveedor DESC
                LIMIT 5
            """)
            stats['top_proveedores'] = []
            for row in cursor.fetchall():
                stats['top_proveedores'].append({
                    'razon_social': row[0],
                    'cantidad': row[1],
                    'total_proveedor': row[2]
                })

            # Facturas por mes últimos 12 meses
            cursor.execute("""
                SELECT 
                    strftime('%Y-%m', created_at) as mes,
                    COUNT(*) as cantidad,
                    COALESCE(SUM(total), 0) as total_mes
                FROM facturas
                WHERE created_at >= date('now', '-12 months')
                GROUP BY strftime('%Y-%m', created_at)
                ORDER BY mes DESC
                LIMIT 12
            """)
            stats['facturas_por_mes'] = []
            for row in cursor.fetchall():
                stats['facturas_por_mes'].append({
                    'mes': row[0],
                    'cantidad': row[1],
                    'total_mes': row[2]
                })

            logger.info(f"Estadísticas generadas: {stats['total_facturas']} facturas, {len(stats['top_proveedores'])} proveedores")
            return stats

        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {
                'total_facturas': 0,
                'suma_total': 0,
                'suma_total_formateada': '$0,00',
                'top_proveedores': [],
                'facturas_por_mes': []
            }