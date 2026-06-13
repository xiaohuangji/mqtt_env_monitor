#ifndef SENSOR_DATA_H
#define SENSOR_DATA_H

#include <Arduino.h>

struct SensorData
{
    String node_id;
    String data_type;
    float value;
    String unit;
    String timestamp;
    unsigned long seq;
};

#endif