// Solo banco, sin electrodos conectados a personas. No transmite LO ni tiempos.
void setup() {
  // Inicializamos a la misma velocidad que en el script de Python
  Serial.begin(115200);
}

void loop() {
  // Leemos el pin analógico y lo enviamos sin modificaciones
  Serial.println(analogRead(A0));
  
  // 10ms = 100 Hz de frecuencia de muestreo (suficiente para graficar en Python)
  delay(10);
}
