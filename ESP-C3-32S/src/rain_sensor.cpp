#include "rain_sensor.h"
#include "config.h"

void initRainSensor()
{
    pinMode(RAIN_PIN, INPUT);
}

SensorData readRainSensor(const String& nodeId, const String& timestamp, unsigned long seq)
{
    int rawValue = analogRead(RAIN_PIN);

    SensorData data;
    data.node_id = nodeId;
    data.data_type = "rain";
    data.value = rawValue;
    data.unit = "raw";
    data.timestamp = timestamp;
    data.seq = seq;

    return data;
}