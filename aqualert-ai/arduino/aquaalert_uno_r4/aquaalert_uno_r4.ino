namespace {

constexpr uint8_t TRIG_PIN = 9;
constexpr uint8_t ECHO_PIN = 10;

constexpr unsigned long SERIAL_BAUD = 115200;
constexpr unsigned long SAMPLE_INTERVAL_MS = 1500;
constexpr unsigned long ECHO_TIMEOUT_US = 30000;
constexpr uint8_t SAMPLE_COUNT = 5;

// Replace these with your real tank calibration values after the first test.
// FULL_DISTANCE_CM  = sensor-to-water distance when the tank is full.
// EMPTY_DISTANCE_CM = sensor-to-water distance when the tank is at its lowest
// normal level right before a refill.
constexpr float FULL_DISTANCE_CM = 5.0f;
constexpr float EMPTY_DISTANCE_CM = 18.0f;

constexpr float WATCH_SPREAD_CM = 1.2f;
constexpr float LOW_FILL_PERCENT = 40.0f;
constexpr float CRITICAL_FILL_PERCENT = 20.0f;

unsigned long lastSampleAtMs = 0;
unsigned long sequenceNumber = 0;

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  unsigned long durationUs = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (durationUs == 0) {
    return -1.0f;
  }

  return (durationUs * 0.0343f) / 2.0f;
}

void sortAscending(float values[], uint8_t count) {
  for (uint8_t i = 0; i < count; ++i) {
    for (uint8_t j = i + 1; j < count; ++j) {
      if (values[j] < values[i]) {
        float tmp = values[i];
        values[i] = values[j];
        values[j] = tmp;
      }
    }
  }
}

float clampFloat(float value, float minValue, float maxValue) {
  if (value < minValue) {
    return minValue;
  }
  if (value > maxValue) {
    return maxValue;
  }
  return value;
}

const char* classifyStatus(float fillPercent, float spreadCm) {
  if (spreadCm > WATCH_SPREAD_CM) {
    return "watch";
  }
  if (fillPercent <= CRITICAL_FILL_PERCENT) {
    return "critical";
  }
  if (fillPercent <= LOW_FILL_PERCENT) {
    return "low";
  }
  return "normal";
}

void printReadingJson(float distanceCm, float fillDepthCm, float tankDepthCm, float fillPercent,
                      float confidence, float spreadCm, uint8_t validSamples, const char* status) {
  Serial.print("{\"arduino_sequence\":");
  Serial.print(sequenceNumber);
  Serial.print(",\"uptime_ms\":");
  Serial.print(millis());
  Serial.print(",\"distance_cm\":");
  Serial.print(distanceCm, 2);
  Serial.print(",\"fill_depth_cm\":");
  Serial.print(fillDepthCm, 2);
  Serial.print(",\"tank_depth_cm\":");
  Serial.print(tankDepthCm, 2);
  Serial.print(",\"fill_percent\":");
  Serial.print(fillPercent, 1);
  Serial.print(",\"status\":\"");
  Serial.print(status);
  Serial.print("\",\"confidence\":");
  Serial.print(confidence, 2);
  Serial.print(",\"sample_count\":");
  Serial.print(validSamples);
  Serial.print(",\"spread_cm\":");
  Serial.print(spreadCm, 2);
  Serial.println("}");
}

void printSensorFaultJson() {
  Serial.print("{\"arduino_sequence\":");
  Serial.print(sequenceNumber);
  Serial.print(",\"uptime_ms\":");
  Serial.print(millis());
  Serial.print(",\"distance_cm\":0.0");
  Serial.print(",\"fill_depth_cm\":0.0");
  Serial.print(",\"tank_depth_cm\":");
  Serial.print(EMPTY_DISTANCE_CM - FULL_DISTANCE_CM, 2);
  Serial.println(",\"fill_percent\":0.0,\"status\":\"sensor_fault\",\"confidence\":0.0,\"sample_count\":0,\"spread_cm\":0.0}");
}

}  // namespace

void setup() {
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  Serial.begin(SERIAL_BAUD);
  delay(1500);
}

void loop() {
  if (millis() - lastSampleAtMs < SAMPLE_INTERVAL_MS) {
    return;
  }
  lastSampleAtMs = millis();
  sequenceNumber++;

  float samples[SAMPLE_COUNT];
  uint8_t validSamples = 0;

  for (uint8_t i = 0; i < SAMPLE_COUNT; ++i) {
    float distanceCm = readDistanceCm();
    if (distanceCm > 0.0f) {
      samples[validSamples++] = distanceCm;
    }
    delay(60);
  }

  if (validSamples < 3) {
    printSensorFaultJson();
    return;
  }

  sortAscending(samples, validSamples);

  float sum = 0.0f;
  float minSample = samples[0];
  float maxSample = samples[validSamples - 1];
  for (uint8_t i = 0; i < validSamples; ++i) {
    sum += samples[i];
  }

  float distanceCm = sum / validSamples;
  float spreadCm = maxSample - minSample;
  float tankDepthCm = EMPTY_DISTANCE_CM - FULL_DISTANCE_CM;
  if (tankDepthCm <= 0.0f) {
    printSensorFaultJson();
    return;
  }
  float fillDepthCm = EMPTY_DISTANCE_CM - distanceCm;
  float fillPercent = tankDepthCm <= 0.0f
    ? 0.0f
    : (fillDepthCm / tankDepthCm) * 100.0f;

  fillDepthCm = clampFloat(fillDepthCm, 0.0f, tankDepthCm);
  fillPercent = clampFloat(fillPercent, 0.0f, 100.0f);

  float confidence = clampFloat(1.0f - (spreadCm / 3.0f), 0.05f, 0.99f);
  const char* status = classifyStatus(fillPercent, spreadCm);

  printReadingJson(distanceCm, fillDepthCm, tankDepthCm, fillPercent, confidence, spreadCm, validSamples, status);
}
