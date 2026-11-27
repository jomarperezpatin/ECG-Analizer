#include <Arduino.h>
#include <string.h>

// Protocolo ECG/1. Solo pruebas de banco, sin electrodos en personas.
const uint16_t FS = 100; // 10 ms, como el sketch original. También se admite 250 Hz.
const uint32_t PERIOD_US = 1000000UL / FS;
const bool CHECK_LEADS = true; // Activar solo tras confirmar el cableado.
const uint8_t LO_PLUS = 10, LO_MINUS = 11;
bool streaming = false, plotOnly = false;
uint32_t nextSample = 0, seq = 0, origin = 0;
char command[24];
uint8_t length = 0;
bool overflow = false;

void handleCommand() {
  if (!strcmp(command, "HELLO")) {
    streaming = false; plotOnly = false;
    Serial.print(F("ECG,1,")); Serial.println(FS);
  } else if (!strcmp(command, "START") || !strcmp(command, "PLOT")) {
    streaming = false;
    plotOnly = !strcmp(command, "PLOT");
    if (!plotOnly) Serial.println(F("OK,START"));
    seq = 0;
    origin = micros(); nextSample = origin;
    streaming = true;
  } else if (!strcmp(command, "STOP")) {
    streaming = false; plotOnly = false;
    Serial.println(F("OK,STOP"));
  } else {
    Serial.println(F("ERR,COMMAND"));
  }
}
void setup() {
  Serial.begin(115200);
  analogReference(DEFAULT);
  pinMode(A0, INPUT);
  if (CHECK_LEADS) {
    pinMode(LO_PLUS, INPUT);
    pinMode(LO_MINUS, INPUT);
  }
}
void loop() {
  // Limitar el trabajo de lectura por iteracion.
  for (uint8_t i=0; i<32 && Serial.available(); ++i) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (overflow) Serial.println(F("ERR,COMMAND"));
      else { command[length] = '\0'; handleCommand(); }
      length=0; overflow=false;
    } else if (!overflow) {
      if (length < sizeof(command)-1) command[length++] = c;
      else overflow=true;
    }
  }
  if (!streaming) return;
  uint32_t now = micros();
  if ((int32_t)(now-nextSample) < 0) return;
  uint32_t missed = (now-nextSample)/PERIOD_US;
  seq += missed;
  nextSample += (missed+1)*PERIOD_US;
  uint32_t stamp = micros()-origin;
  int value = analogRead(A0);
  int lead = CHECK_LEADS ? (digitalRead(LO_PLUS)==HIGH || digitalRead(LO_MINUS)==HIGH ? 1 : 0) : -1;
  // PLOT: raw ADC only, as in the reference sketch. Bench diagnostics only.
  if (plotOnly) {
    if (stamp >= 60000000UL) { streaming = false; plotOnly = false; return; }
    Serial.println(value); seq++; return;
  }
  Serial.print(F("DATA,")); Serial.print(seq++); Serial.print(',');
  Serial.print(stamp); Serial.print(','); Serial.print(value); Serial.print(','); Serial.println(lead);
}
