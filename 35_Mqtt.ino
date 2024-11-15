#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include "config.h"              // Datos de la red WiFi
#include "MQTT.hpp"
#include "ESP8266_Utils.hpp"
#include "ESP8266_Utils_MQTT.hpp"

const int trigPin = D5;          // Pin de Trigger
const int echoPin = D6;          // Pin de Echo
const int ledRojo = D3;          // Pin del LED rojo
const int ledVerde = D2;         // Pin del LED verde
const int ledAzul = D1;          // Pin del LED azul en el LED RGB

void setup(void) {
  Serial.begin(115200);
  SPIFFS.begin();

  // Configuración de pines
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(ledRojo, OUTPUT);
  pinMode(ledVerde, OUTPUT);
  pinMode(ledAzul, OUTPUT);      // Configuración del LED azul

  // Conexión a WiFi
  ConnectWiFi_STA(false);
  
  InitMqtt();
}

void loop() {
  
  HandleMqtt();  // Mantiene la conexión MQTT

  // Enviar pulso al sensor ultrasónico
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  // Leer distancia del sensor
  long duration = pulseIn(echoPin, HIGH);
  int distance = duration * 0.034 / 2;

  // Imprimir la distancia en el Monitor Serial
  Serial.print("Distancia medida: ");
  Serial.print(distance);
  Serial.println(" cm");

  // Control de LEDs según la distancia
  if (distance <= 3) {
    digitalWrite(ledRojo, HIGH);   // Enciende el LED rojo
    digitalWrite(ledVerde, LOW);   // Apaga el LED verde
  } else {
    digitalWrite(ledRojo, LOW);    // Apaga el LED rojo
    digitalWrite(ledVerde, HIGH);  // Enciende el LED verde
  }

  // Lógica para el LED azul del LED RGB
  if (distance >= 20) {
    digitalWrite(ledAzul, HIGH);   // Enciende el LED azul
  } else {
    digitalWrite(ledAzul, LOW);    // Apaga el LED azul
  }

  // Publicar la distancia en el tópico MQTT
  char msg[50];
  snprintf(msg, 50, "Distancia medida: %d cm", distance);
  PublisMqtt(distance);

  delay(200);  // Espera antes de la próxima lectura
}