#include "dht11_sensor.h"
#include "config.h"
#include <DHT.h>

#define DHT_TYPE DHT11

DHT dht(DHT11_PIN, DHT_TYPE);

float lastTemperature = 0;
float lastHumidity = 0;
bool lastReadValid = false;

// =======================
// 初始化 DHT11
// =======================
void initDHT11Sensor()
{
    dht.begin();
}

// =======================
// 读取一次 DHT11 数据
// 由于 DHT11 一次可以同时读取温度和湿度，
// 所以这里统一读取后保存，供温度和湿度函数使用
// =======================
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

// =======================
// 读取温度数据
// =======================
SensorData readDHT11Temperature(const String& nodeId, const String& timestamp, unsigned long seq)
{
    updateDHT11Data();

    SensorData data;
    data.node_id = nodeId;
    data.data_type = "temperature";
    data.value = lastTemperature;
    data.unit = "C";
    data.timestamp = timestamp;
    data.seq = seq;

    if (!lastReadValid)
    {
        data.value = -1;
    }

    return data;
}

// =======================
// 读取湿度数据
// =======================
SensorData readDHT11Humidity(const String& nodeId, const String& timestamp, unsigned long seq)
{
    SensorData data;
    data.node_id = nodeId;
    data.data_type = "humidity";
    data.value = lastHumidity;
    data.unit = "%";
    data.timestamp = timestamp;
    data.seq = seq;

    if (!lastReadValid)
    {
        data.value = -1;
    }

    return data;
}