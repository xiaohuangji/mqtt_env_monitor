#include "dht11_sensor.h"
#include "config.h"

#include <DHT.h>

#define DHT_TYPE DHT11

DHT dht(DHT11_PIN, DHT_TYPE);

float lastTemperature = 0.0;
float lastHumidity = 0.0;
bool lastReadValid = false;

void initDHT11Sensor()
{
    dht.begin();
}

void updateDHT11Data()
{
    float temperature = dht.readTemperature();
    float humidity = dht.readHumidity();

    if (isnan(temperature) || isnan(humidity))
    {
        lastReadValid = false;
        return;
    }

    lastTemperature = temperature;
    lastHumidity = humidity;
    lastReadValid = true;
}

SensorData readDHT11Temperature(const String& nodeId, const String& timestamp, unsigned long seq)
{
    updateDHT11Data();

    SensorData data;

    data.node_id = nodeId;
    data.data_type = "temperature";
    data.value = lastReadValid ? lastTemperature : -1;
    data.unit = "C";
    data.timestamp = timestamp;
    data.seq = seq;

    return data;
}

SensorData readDHT11Humidity(const String& nodeId, const String& timestamp, unsigned long seq)
{
    SensorData data;

    data.node_id = nodeId;
    data.data_type = "humidity";
    data.value = lastReadValid ? lastHumidity : -1;
    data.unit = "%";
    data.timestamp = timestamp;
    data.seq = seq;

    return data;
}