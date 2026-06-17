#ifndef DHT11_SENSOR_H
#define DHT11_SENSOR_H

#include <Arduino.h>
#include "sensor_data.h"

void initDHT11Sensor();

SensorData readDHT11Temperature(const String& nodeId, const String& timestamp, unsigned long seq);

SensorData readDHT11Humidity(const String& nodeId, const String& timestamp, unsigned long seq);

#endif