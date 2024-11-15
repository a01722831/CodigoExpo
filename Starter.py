import sys
import threading
import paho.mqtt.client as paho
import time
import signal
import mysql.connector
from mysql.connector import errorcode

# Variables de conexión a la base de datos
host = "localhost"
user = "root"
password = "Chelo044"
database_name = "ParkingDB"
table_distancias = "Distancias"
table_historial = "Historial"

# Inicialización de parámetros
NUM_REPETICIONES = 100  # Número de mediciones consecutivas para Distancias
NUM_REPETICIONES2 = 10  # Número de mediciones consecutivas para cambiar el estado en Historial
recent_measurements = {i: {'value': None, 'count': 0} for i in range(1, 6)}

# Variables de estado para Historial
sensor_3_measurements = []
last_inserted_value = 0  # El último valor insertado, comenzando con 0

# Inicializar base de datos y tabla
try:
    cnx = mysql.connector.connect(host=host, user=user, password=password)
    cursor = cnx.cursor()

    # Crear la base de datos si no existe
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database_name}")
    cnx.database = database_name

    # Crear la tabla Distancias
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_distancias} (
            sensorNum INT NOT NULL, 
            distanceMed INT NOT NULL
        )
    """)
    print(f"Tabla '{table_distancias}' lista.")

    # Crear la tabla Historial
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_historial} (
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            Estatus INT NOT NULL
        )
    """)
    print(f"Tabla '{table_historial}' lista.")

    # Insertar estado inicial en Historial
    cursor.execute(f"INSERT INTO {table_historial} (Estatus) VALUES (0)")
    cnx.commit()
    print("Estado inicial 0 insertado en Historial.")

except mysql.connector.Error as err:
    print(f"Error: {err}")
finally:
    cursor.close()
    cnx.close()


# Función para alternar y actualizar estatus en la tabla Historial
def alternar_estatus():
    global last_inserted_value
    nuevo_estatus = 1 if last_inserted_value == 0 else 0

    try:
        cnx = mysql.connector.connect(host=host, user=user, password=password, database=database_name)
        cursor = cnx.cursor()

        # Insertar nuevo estatus alternante
        cursor.execute(f"INSERT INTO {table_historial} (Estatus) VALUES (%s)", (nuevo_estatus,))
        cnx.commit()

        # Actualizar el último valor insertado
        last_inserted_value = nuevo_estatus
        print(f"Insertado en Historial: Estatus {nuevo_estatus}.")

    except mysql.connector.Error as err:
        print(f"Error de base de datos: {err}")
    finally:
        cursor.close()
        cnx.close()


# Función para insertar datos en la tabla Distancias
def insert_into_distancias(sensor_num, distance):
    if recent_measurements[sensor_num]['value'] == distance:
        recent_measurements[sensor_num]['count'] += 1
    else:
        recent_measurements[sensor_num] = {'value': distance, 'count': 1}

    # Insertar en Distancias si la distancia es igual en NUM_REPETICIONES consecutivas
    if recent_measurements[sensor_num]['count'] >= NUM_REPETICIONES:
        try:
            cnx = mysql.connector.connect(host=host, user=user, password=password, database=database_name)
            cursor = cnx.cursor()

            # Insertar medida en Distancias
            cursor.execute(f"INSERT INTO {table_distancias} (sensorNum, distanceMed) VALUES (%s, %s)",
                           (sensor_num, distance))
            cnx.commit()
            print(f"Valor {distance} de sensor {sensor_num} insertado en '{table_distancias}'.")

            # Resetear contador
            recent_measurements[sensor_num]['count'] = 0

        except mysql.connector.Error as err:
            print(f"Error de base de datos: {err}")
        finally:
            cursor.close()
            cnx.close()

    # Solo alternar el estatus en Historial para el sensor 3
    if sensor_num == 3:
        verificar_y_actualizar_historial(sensor_num, distance)


# Variable para almacenar la última medición que causó un cambio en Historial
last_triggered_measurement = None

# Función para verificar el estado de Historial para el sensor 3
def verificar_y_actualizar_historial(sensor_num, distance):
    global sensor_3_measurements, last_triggered_measurement

    # Agregar la medición actual de sensor 3
    if len(sensor_3_measurements) > 0 and sensor_3_measurements[-1] == distance:
        sensor_3_measurements.append(distance)
    else:
        sensor_3_measurements = [distance]  # Reiniciar mediciones consecutivas con un valor nuevo

    # Alternar estatus si se han cumplido NUM_REPETICIONES2 de sensor 3 con un valor nuevo
    if len(sensor_3_measurements) >= NUM_REPETICIONES2:
        # Solo insertamos si la medición es distinta a la última que causó un cambio
        if distance != last_triggered_measurement:
            alternar_estatus()
            last_triggered_measurement = distance  # Actualizar con la nueva medición que causa cambio

        sensor_3_measurements.clear()  # Reiniciar lista para el siguiente grupo de mediciones


# Definir función de manejo de mensajes para cada cliente
def message_handling(client_idx):
    def handler(client, userdata, msg):
        global data
        data[client_idx] = msg.payload.decode()
        insert_into_distancias(client_idx + 1, int(data[client_idx]))  # Insertar con el número de sensor

    return handler


# Inicializar y conectar clientes MQTT
clients = [paho.Client() for _ in range(5)]
data = [None] * 5
apprun = True

# Asignar manejadores y suscribirse a temas
for i in range(5):
    clients[i].on_message = message_handling(i)
    if clients[i].connect("localhost", 1883, 60) != 0:
        print(f"No se pudo conectar el cliente {i + 1} al broker MQTT")
        exit(1)
    clients[i].subscribe(f"arduino_{i + 1}/hello_esp8266")


# Manejo de señal para salida limpia
def signal_handler(sig, frame):
    global clients
    print('Se presionó Ctrl+C!')
    for client in clients:
        client.disconnect()
    print("Saliendo")
    exit(0)


signal.signal(signal.SIGINT, signal_handler)

# Ejecutar bucles de clientes en hilos separados
try:
    print("Presiona CTRL+C para salir...")
    threads = [threading.Thread(target=clients[i].loop_forever) for i in range(5)]

    for thread in threads:
        thread.start()

    while apprun:
        try:
            time.sleep(0.5)
            for i, d in enumerate(data):
                print(f"data{i + 1}: {d}")
            print("----")
        except KeyboardInterrupt:
            print("Desconectando")
            apprun = False
            for client in clients:
                client.disconnect()
            time.sleep(1)

    for thread in threads:
        thread.join()

except Exception as e:
    print(f"Se atrapó una excepción: {e}")
