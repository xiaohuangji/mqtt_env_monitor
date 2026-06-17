#include <Arduino.h>

#include "config.h"
#include "sensor_data.h"

#include "dht11_sensor.h"
#include "light_sensor.h"
#include "mq2_sensor.h"
#include "soil_sensor.h"

#include "wifi_config.h"
#include "time_sync.h"
#include "mqtt_client.h"

// =======================
// 全局变量
// =======================

unsigned long lastCollectTime = 0;
unsigned long lastWiFiCheckTime = 0;
unsigned long lastMqttCheckTime = 0;

unsigned long seq = 1;

bool timeInitFinished = false;
bool mqttInitFinished = false;


// =======================
// 初始化传感器
// =======================
void initSensors()
{
    // GPIO5：DHT11 温湿度传感器
    initDHT11Sensor();

    // GPIO1 / GPIO2：GY-302 / BH1750 光照度传感器
    initLightSensor();

    // GPIO3：FC-28 土壤湿度传感器
    initSoilSensor();

    // GPIO4：MQ-2 气体传感器
    initMQ2Sensor();
}


// =======================
// 采集并通过 MQTT 发布数据
// Topic：env_monitor/{node_id}/{data_type}
// Payload：{"n":"esp32hyh0614","d":"light","v":123.45,"t":epoch毫秒,"s":序号}
// =======================
void collectAndPublishSensorData()
{
    Serial.println();
    Serial.println("========== Sensor Data MQTT Publish ==========");

    Serial.print("[WiFi] Status: ");
    Serial.println(getWiFiStatusText());

    Serial.print("[MQTT] Status: ");
    Serial.println(isMqttConnected() ? "connected" : "disconnected");

    // 1. DHT11 温度
    SensorData temperatureData = readDHT11Temperature(NODE_ID, "", seq++);
    publishSensorDataQoS1(temperatureData);

    // 2. DHT11 湿度
    SensorData humidityData = readDHT11Humidity(NODE_ID, "", seq++);
    publishSensorDataQoS1(humidityData);

    // 3. BH1750 光照度
    SensorData lightData = readLightSensor(NODE_ID, "", seq++);
    publishSensorDataQoS1(lightData);

    // 4. MQ-2 烟雾 / 气体原始 ADC 值
    SensorData smokeData = readMQ2Sensor(NODE_ID, "", seq++);
    publishSensorDataQoS1(smokeData);

    // 5. FC-28 土壤湿度百分比
    SensorData soilData = readSoilSensor(NODE_ID, "", seq++);
    publishSensorDataQoS1(soilData);

    Serial.println("==============================================");
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
    Serial.println("Mode: WiFiManager + NTP + MQTT QoS1 Publish");
    Serial.println("Broker: broker.emqx.io:1883");
    Serial.println("MQTT Version: 3.1.1");
    Serial.println("MQTT QoS: 1");
    Serial.println("MQTT Keepalive: 30 s");
    Serial.println("Topic: env_monitor/{node_id}/{data_type}");
    Serial.println("Node ID: esp32hyh0614");
    Serial.println("============================================");

    /*
     * 如需重新配置 WiFi，可临时取消下面这句注释：
     *
     * clearSavedWiFiConfig();
     *
     * 上传运行一次后，ESP32 会清除已保存 WiFi 并重新进入配网模式。
     * 配网成功后，一定要重新注释掉或删除该语句。
     */
    // clearSavedWiFiConfig();

    // 初始化 WiFiManager 配网
    initWiFiConfig();

    // 初始化传感器
    initSensors();

    Serial.println();
    Serial.println("[Sensor] Sensor init finished.");
    Serial.println("[Sensor] GPIO5: DHT11 temperature and humidity");
    Serial.println("[Sensor] GPIO1: BH1750 SDA");
    Serial.println("[Sensor] GPIO2: BH1750 SCL");
    Serial.println("[Sensor] GPIO3: FC-28 soil moisture");
    Serial.println("[Sensor] GPIO4: MQ-2 smoke sensor");
    Serial.println("[Sensor] Publish order: temperature -> humidity -> light -> smoke -> soil_moisture");
}


// =======================
// loop 主循环
// =======================
void loop()
{
    // 1. 处理 WiFi 状态监测、断线重连、重新配网
    handleWiFiConfig();

    // 2. WiFi 未连接时，不进行 NTP、MQTT 和传感器采集
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

    // 3. WiFi 已连接后，同步一次 NTP 时间
    if (!timeInitFinished)
    {
        initTimeSync();
        timeInitFinished = true;

        if (!isTimeSynced())
        {
            Serial.println("[Time] NTP sync failed, sensor collection paused.");
            Serial.println("[Time] Please check network connection or NTP server.");
        }
    }

    // 4. 时间未同步成功时，不采集、不发布
    if (!isTimeSynced())
    {
        return;
    }

    // 5. 初始化 MQTT 客户端
    if (!mqttInitFinished)
    {
        initMqttClient();
        mqttInitFinished = true;
    }

    // 6. 维护 MQTT 连接
    handleMqttClient();

    // 7. MQTT 未连接时，不发布数据
    if (!isMqttConnected())
    {
        unsigned long now = millis();

        if (now - lastMqttCheckTime >= 5000)
        {
            lastMqttCheckTime = now;

            Serial.println("[MQTT] Not connected, sensor publish paused.");
            Serial.println("[MQTT] Waiting for reconnect to broker broker.emqx.io:1883.");
        }

        return;
    }

    unsigned long now = millis();

    // 8. WiFi、NTP、MQTT 都正常后，每 30 秒采集并发布一次
    if (now - lastCollectTime >= COLLECT_INTERVAL_MS)
    {
        lastCollectTime = now;
        collectAndPublishSensorData();
    }
}