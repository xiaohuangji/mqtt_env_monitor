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

    // 按照联调规范，MQ-2 的 data_type 统一为 smoke
    data.data_type = "smoke";

    // MQ-2 当前使用原始 ADC 值
    data.value = rawValue;
    data.unit = "raw";
    data.timestamp = timestamp;
    data.seq = seq;

    return data;
}