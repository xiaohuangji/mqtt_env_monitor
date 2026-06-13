#include "mq2_sensor.h"
#include "config.h"

void initMQ2Sensor()
{
    pinMode(MQ2_PIN, INPUT);
}

SensorData readMQ2Sensor(const String& nodeId, const String& timestamp, unsigned long seq)
{
    int rawValue = analogRead(MQ2_PIN);

    SensorData data;
    data.node_id = nodeId;
    data.data_type = "mq2_gas";
    data.value = rawValue;
    data.unit = "raw";
    data.timestamp = timestamp;
    data.seq = seq;

    return data;
}