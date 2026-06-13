#ifndef SOIL_SENSOR_H
#define SOIL_SENSOR_H

#include <Arduino.h>
#include "sensor_data.h"

void initSoilSensor();
SensorData readSoilSensor(const String& nodeId, const String& timestamp, unsigned long seq);

#endif