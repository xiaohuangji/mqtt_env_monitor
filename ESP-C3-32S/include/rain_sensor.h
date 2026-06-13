#ifndef RAIN_SENSOR_H
#define RAIN_SENSOR_H

#include <Arduino.h>
#include "sensor_data.h"

void initRainSensor();
SensorData readRainSensor(const String& nodeId, const String& timestamp, unsigned long seq);

#endif