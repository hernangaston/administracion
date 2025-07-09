import sqlite3
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar OpenAI

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
        
        INSTRUCCIONES:
        1. Genera SOLO la consulta SQL, sin explicaciones
        2. Usa SQLite syntax
        3. Para fechas usa strftime y DATE()
        4. Para búsquedas de texto usa LIKE con %
        5. Limita resultados a 50 con LIMIT
        6. Ordena por fecha más reciente (ORDER BY created_at DESC)
        
        EJEMPLOS:
        - "facturas de enero" -> SELECT * FROM facturas WHERE strftime('%m', created_at) = '01' ORDER BY created_at DESC LIMIT 50
        - "facturas mayores a 100000" -> SELECT * FROM facturas WHERE total > 100000 ORDER BY created_at DESC LIMIT 50
        - "facturas de mercado libre" -> SELECT * FROM facturas WHERE razon_social LIKE '%mercado%libre%' ORDER BY created_at DESC LIMIT 50
        
        SQL:
        """

        try:
            response = client.chat.completions.create(model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.1)

            sql_query = response.choices[0].message.content.strip()

            # Limpiar la respuesta
            sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

            logger.info(f"SQL generado: {sql_query}")
            return sql_query

        except Exception as e:
            logger.error(f"Error generando SQL: {e}")
            # Consulta por defecto
            return "SELECT * FROM facturas ORDER BY created_at DESC LIMIT 10"

    def _ejecutar_consulta_sql(self, sql_query: str) -> List[Dict]:
        """
        Ejecuta la consulta SQL de forma segura
        """
        try:
            # Validaciones de seguridad básicas
            sql_lower = sql_query.lower()
            palabras_prohibidas = ['drop', 'delete', 'update', 'insert', 'alter', 'create']

            for palabra in palabras_prohibidas:
                if palabra in sql_lower:
                    raise ValueError(f"Operación no permitida: {palabra}")

            cursor = self.db.cursor()
            cursor.execute(sql_query)

            resultados = []
            for row in cursor.fetchall():
                # Convertir sqlite3.Row a diccionario
                resultado = dict(row)

                # Formatear datos para mejor presentación
                if resultado.get('total'):
                    resultado['total_formateado'] = f"${resultado['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

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
            suma_total = sum(float(r.get('total', 0)) for r in resultados if r.get('total'))

            # Obtener algunos ejemplos
            ejemplos = []
            for i, resultado in enumerate(resultados[:3]):
                razon_social = resultado.get('razon_social', 'Sin nombre')
                total = resultado.get('total_formateado', 'N/A')
                fecha = resultado.get('fecha_formateada', 'N/A')
                ejemplos.append(f"• {razon_social} - {total} ({fecha})")

            prompt = f"""
            Genera una respuesta natural y útil basada en estos datos:
            
            CONSULTA ORIGINAL: "{consulta_original}"
            RESULTADOS ENCONTRADOS: {total_facturas} facturas
            SUMA TOTAL: ${suma_total:,.2f}
            
            EJEMPLOS:
            {chr(10).join(ejemplos)}
            
            INSTRUCCIONES:
            1. Responde en español de forma natural y amigable
            2. Menciona la cantidad de facturas encontradas
            3. Si hay suma total significativa, menciónala
            4. Da 2-3 ejemplos específicos
            5. Mantén la respuesta concisa pero informativa
            6. Usa un tono profesional pero cercano
            
            RESPUESTA:
            """

            response = client.chat.completions.create(model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3)

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generando respuesta natural: {e}")
            return f"Encontré {len(resultados)} facturas que coinciden con tu consulta."

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
        Genera estadísticas inteligentes sobre las facturas
        """
        try:
            cursor = self.db.cursor()

            # Estadísticas básicas
            cursor.execute("SELECT COUNT(*) as total FROM facturas")
            total_facturas = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(total) as suma_total FROM facturas WHERE total IS NOT NULL")
            suma_total = cursor.fetchone()[0] or 0

            # Top 5 proveedores
            cursor.execute("""
                SELECT razon_social, COUNT(*) as cantidad, SUM(total) as total_proveedor
                FROM facturas 
                WHERE razon_social IS NOT NULL
                GROUP BY razon_social
                ORDER BY total_proveedor DESC
                LIMIT 5
            """)
            top_proveedores = [dict(row) for row in cursor.fetchall()]

            # Facturas por mes
            cursor.execute("""
                SELECT strftime('%Y-%m', created_at) as mes, COUNT(*) as cantidad
                FROM facturas
                GROUP BY mes
                ORDER BY mes DESC
                LIMIT 12
            """)
            por_mes = [dict(row) for row in cursor.fetchall()]

            return {
                "total_facturas": total_facturas,
                "suma_total": suma_total,
                "suma_total_formateada": f"${suma_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "top_proveedores": top_proveedores,
                "facturas_por_mes": por_mes
            }

        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {}