#include "light_sensor.h"
#include "config.h"

#include <Wire.h>
#include <BH1750.h>

BH1750 lightMeter;

bool lightSensorReady = false;

void initLightSensor()
{
    Serial.println("[BH1750] Init light sensor...");

    // ESP32-C3 指定 I2C 引脚
    Wire.begin(BH1750_SDA_PIN, BH1750_SCL_PIN);

    // BH1750 默认 I2C 地址一般为 0x23
    if (lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE))
    {
        lightSensorReady = true;
        Serial.println("[BH1750] Light sensor init success.");
        Serial.print("[BH1750] SDA GPIO: ");
        Serial.println(BH1750_SDA_PIN);
        Serial.print("[BH1750] SCL GPIO: ");
        Serial.println(BH1750_SCL_PIN);
    }
    else
    {
        lightSensorReady = false;
        Serial.println("[BH1750] Light sensor init failed.");
        Serial.println("[BH1750] Please check VCC, GND, SDA, SCL wiring.");
    }
}

SensorData readLightSensor(const String& nodeId, const String& timestamp, unsigned long seq)
{
    SensorData data;

    data.node_id = nodeId;
    data.data_type = "light";
    data.unit = "lux";
    data.timestamp = timestamp;
    data.seq = seq;

    if (!lightSensorReady)
    {
        data.value = -1.0;
        Serial.println("[BH1750] Sensor not ready, light value = -1.");
        return data;
    }

    float lux = lightMeter.readLightLevel();

    if (lux < 0)
    {
        data.value = -1.0;
        Serial.println("[BH1750] Read failed, light value = -1.");
    }
    else
    {
        data.value = lux;

        Serial.print("[BH1750] Light: ");
        Serial.print(lux);
        Serial.println(" lux");
    }

    return data;
}