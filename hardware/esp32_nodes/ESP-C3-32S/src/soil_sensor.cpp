#include "soil_sensor.h"
#include "config.h"

// 土壤湿度标定值
// SOIL_DRY_RAW：干燥状态 ADC 值，对应 0%
// SOIL_WET_RAW：潮湿/水中状态 ADC 值，对应 100%
#define SOIL_DRY_RAW 4095.0
#define SOIL_WET_RAW 1690.0

void initSoilSensor()
{
    pinMode(SOIL_PIN, INPUT);
}

SensorData readSoilSensor(const String& nodeId, const String& timestamp, unsigned long seq)
{
    int rawValue = analogRead(SOIL_PIN);

    float percent = (SOIL_DRY_RAW - rawValue) * 100.0 / (SOIL_DRY_RAW - SOIL_WET_RAW);

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