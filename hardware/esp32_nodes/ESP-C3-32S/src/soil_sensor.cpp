#include "soil_sensor.h"
#include "config.h"

void initSoilSensor()
{
    pinMode(SOIL_PIN, INPUT);
}

SensorData readSoilSensor(const String& nodeId, const String& timestamp, unsigned long seq)
{
    int rawValue = analogRead(SOIL_PIN);

    // 简单换算为百分比，方便串口观察
    // 4095 为干燥空气中的 ADC 值，对应土壤湿度 0%
    // 1690 为水中的 ADC 值，对应土壤湿度 100%
    float percent = map(rawValue, 4095, 1690, 0, 100);

    if (percent < 0)
    {
        percent = 0;
    }

    if (percent > 100)
    {
        percent = 100;
    }

    SensorData data;
    data.node_id = nodeId;
    data.data_type = "soil_moisture";
    data.value = percent;
    data.unit = "%";
    data.timestamp = timestamp;
    data.seq = seq;

    return data;
}