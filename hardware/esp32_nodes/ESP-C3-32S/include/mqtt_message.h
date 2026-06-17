#ifndef MQTT_MESSAGE_H
#define MQTT_MESSAGE_H

#include <Arduino.h>
#include "sensor_data.h"

String buildMqttTopic(const SensorData& data);

String buildCompactJsonPayload(const SensorData& data, uint64_t epochMillis);

#endif