#ifndef MQ2_SENSOR_H
#define MQ2_SENSOR_H

#include <Arduino.h>
#include "sensor_data.h"

void initMQ2Sensor();
SensorData readMQ2Sensor(const String& nodeId, const String& timestamp, unsigned long seq);

#endif