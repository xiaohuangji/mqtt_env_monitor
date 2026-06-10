#include <Arduino.h>

#include "config.h"
#include "sensor_data.h"
#include "mq2_sensor.h"
#include "rain_sensor.h"
#include "soil_sensor.h"
#include "mqtt_message.h"

unsigned long lastCollectTime = 0;
unsigned long seq = 1;

// =======================
// 获取时间戳
// 当前没有连接 WiFi，无法获取真实网络时间
// 所以这里使用 millis() 生成本地运行时间戳
// =======================
String getLocalTimestamp()
{
    unsigned long seconds = millis() / 1000;

    String timestamp = "local_time_";
    timestamp += String(seconds);
    timestamp += "s";

    return timestamp;
}

// =======================
// 串口打印数据
// =======================
void printSensorData(const SensorData& data)
{
    String topic = buildMqttTopic(data);
    String payload = buildJsonPayload(data);

    Serial.println("----------------------------------------");
    Serial.print("Topic: ");
    Serial.println(topic);

    Serial.print("Payload: ");
    Serial.println(payload);
}

void setup()
{
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("ESP32-C3 Sensor Data Collection Start");
    Serial.println("Mode: collect sensor data and print JSON only");
    Serial.println("WiFi: disabled");
    Serial.println("MQTT: disabled");

    initMQ2Sensor();
    initRainSensor();
    initSoilSensor();

    Serial.println("Sensor init finished.");
}

void loop()
{
    unsigned long now = millis();

    if (now - lastCollectTime >= COLLECT_INTERVAL_MS)
    {
        lastCollectTime = now;

        String timestamp = getLocalTimestamp();

        SensorData mq2Data = readMQ2Sensor(NODE_ID, timestamp, seq++);
        printSensorData(mq2Data);

        SensorData rainData = readRainSensor(NODE_ID, timestamp, seq++);
        printSensorData(rainData);

        SensorData soilData = readSoilSensor(NODE_ID, timestamp, seq++);
        printSensorData(soilData);
    }
}
