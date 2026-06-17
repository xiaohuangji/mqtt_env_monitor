#include <Arduino.h>

#include "config.h"
#include "sensor_data.h"

#include "dht11_sensor.h"
#include "soil_sensor.h"
#include "mq2_sensor.h"

#include "mqtt_message.h"
#include "wifi_config.h"
#include "time_sync.h"

// =======================
// 全局变量
// =======================

// 上一次采集时间
unsigned long lastCollectTime = 0;

// 上一次 WiFi 未连接提示时间
unsigned long lastWiFiCheckTime = 0;

// 数据序号
unsigned long seq = 1;

// 时间同步标志
bool timeInitFinished = false;


// =======================
// 串口打印传感器数据
// 当前阶段只打印 Topic 和 Payload
// 后续 MQTT 发布时可直接复用
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


// =======================
// 初始化传感器
// 按照规划好的 GPIO 顺序
// GPIO0：DHT11 温湿度传感器
// GPIO1：预留光照传感器
// GPIO2：预留噪声检测模块
// GPIO3：土壤湿度传感器
// GPIO4：MQ-2 气体传感器
// =======================
void initSensors()
{
    // GPIO0：DHT11 温湿度传感器
    initDHT11Sensor();

    // GPIO1：预留光照传感器接口
    pinMode(LIGHT_PIN, INPUT);

    // GPIO2：预留噪声检测模块接口
    pinMode(NOISE_PIN, INPUT);

    // GPIO3：土壤湿度传感器
    initSoilSensor();

    // GPIO4：MQ-2 气体传感器
    initMQ2Sensor();
}


// =======================
// 采集并输出传感器数据
// 只有 WiFi 已连接、北京时间同步成功后才会调用
// 输出顺序：
// 1. 温度
// 2. 湿度
// 3. 光照预留
// 4. 噪声预留
// 5. 土壤湿度
// 6. 气体传感器
// =======================
void collectAndPrintSensorData()
{
    String timestamp = getBeijingTimestamp();

    if (timestamp == "time_not_synced")
    {
        Serial.println("[Time] Time not synced, skip this collection.");
        return;
    }

    Serial.println();
    Serial.println("========== Sensor Data Collection ==========");

    Serial.print("[WiFi] Status: ");
    Serial.println(getWiFiStatusText());

    Serial.print("[Time] Timestamp: ");
    Serial.println(timestamp);

    // 1. GPIO0：DHT11 温度
    SensorData temperatureData = readDHT11Temperature(NODE_ID, timestamp, seq++);
    printSensorData(temperatureData);

    // 2. GPIO0：DHT11 湿度
    SensorData humidityData = readDHT11Humidity(NODE_ID, timestamp, seq++);
    printSensorData(humidityData);

    // 3. GPIO1：光照传感器预留
    // 当前未接入光照传感器，因此暂不采集、不输出

    // 4. GPIO2：噪声检测模块预留
    // 当前未接入噪声检测模块，因此暂不采集、不输出

    // 5. GPIO3：土壤湿度检测模块
    SensorData soilData = readSoilSensor(NODE_ID, timestamp, seq++);
    printSensorData(soilData);

    // 6. GPIO4：MQ-2 气体传感器模块
    SensorData mq2Data = readMQ2Sensor(NODE_ID, timestamp, seq++);
    printSensorData(mq2Data);

    Serial.println("============================================");
}


// =======================
// setup 初始化
// =======================
void setup()
{
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("============================================");
    Serial.println("ESP32-C3 Environment Monitor Start");
    Serial.println("Mode: WiFi config portal + Beijing time + sensor JSON output");
    Serial.println("MQTT: disabled now, topic and payload are ready for later publish");
    Serial.println("============================================");

    // 初始化 WiFi 配网模块
    // 如果已有 WiFi 信息，则自动连接
    // 如果没有 WiFi 信息或连接失败，则启动 AP 配网网页门户
    initWiFiConfig();

    // 初始化传感器
    initSensors();

    Serial.println();
    Serial.println("[Sensor] Sensor init finished.");
    Serial.println("[Sensor] Sensor order: DHT11 -> Light reserved -> Noise reserved -> Soil -> MQ2");
}


// =======================
// loop 主循环
// =======================
void loop()
{
    // 必须放在最前面：
    // 1. 处理 AP 配网页面请求
    // 2. 监测 WiFi 状态
    // 3. WiFi 断线后自动重连
    // 4. 重新连接成功后打印重连耗时
    handleWiFiConfig();

    // WiFi 未连接时，不进行采集
    if (!isWiFiConnected())
    {
        unsigned long now = millis();

        if (now - lastWiFiCheckTime >= 5000)
        {
            lastWiFiCheckTime = now;

            Serial.print("[WiFi] Not connected, sensor collection paused. Status: ");
            Serial.println(getWiFiStatusText());
        }

        return;
    }

    // WiFi 已连接后，只同步一次北京时间
    if (!timeInitFinished)
    {
        initTimeSync();
        timeInitFinished = true;

        if (!isTimeSynced())
        {
            Serial.println("[Time] Time sync failed, sensor collection paused.");
            Serial.println("[Time] Please check network connection or NTP server.");
        }
    }

    // 时间未同步成功时，不采集
    if (!isTimeSynced())
    {
        return;
    }

    unsigned long now = millis();

    // WiFi 连接并且时间同步成功后，每 30 秒采集一次
    if (now - lastCollectTime >= COLLECT_INTERVAL_MS)
    {
        lastCollectTime = now;
        collectAndPrintSensorData();
    }
}