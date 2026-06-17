#include "mqtt_client.h"
#include "config.h"
#include "mqtt_message.h"
#include "time_sync.h"

#include <WiFi.h>
#include <AsyncMqttClient.h>

// =======================
// MQTT 客户端对象
// =======================

AsyncMqttClient mqttClient;

// MQTT 连接状态
bool mqttConnected = false;

// MQTT 初始化标志
bool mqttCallbacksConfigured = false;

// 上一次尝试重连时间
unsigned long lastMqttReconnectAttempt = 0;

// MQTT 重连间隔
#define MQTT_RECONNECT_INTERVAL_MS 5000


// =======================
// MQTT 连接成功回调
// =======================
void onMqttConnect(bool sessionPresent)
{
    mqttConnected = true;

    Serial.println();
    Serial.println("[MQTT] Connected successfully.");
    Serial.print("[MQTT] Session present: ");
    Serial.println(sessionPresent ? "true" : "false");

    Serial.println("[MQTT] MQTT version: 3.1.1");
    Serial.println("[MQTT] Anonymous connection");

    Serial.print("[MQTT] Broker: ");
    Serial.print(MQTT_BROKER_HOST);
    Serial.print(":");
    Serial.println(MQTT_BROKER_PORT);

    Serial.print("[MQTT] Keepalive: ");
    Serial.print(MQTT_KEEPALIVE_SEC);
    Serial.println(" s");

    Serial.print("[MQTT] Publish QoS: ");
    Serial.println(MQTT_QOS_LEVEL);
}


// =======================
// MQTT 断开连接回调
// =======================
void onMqttDisconnect(AsyncMqttClientDisconnectReason reason)
{
    mqttConnected = false;

    Serial.println();
    Serial.println("[MQTT] Disconnected from broker.");
    Serial.print("[MQTT] Disconnect reason code: ");
    Serial.println((int)reason);
}


// =======================
// MQTT 发布确认回调
// QoS 1 时，收到 PUBACK 后会触发该回调
// =======================
void onMqttPublish(uint16_t packetId)
{
    Serial.print("[MQTT] Publish acknowledged, packetId: ");
    Serial.println(packetId);
}


// =======================
// 连接 MQTT Broker
// =======================
void connectMqttBroker()
{
    if (mqttConnected)
    {
        return;
    }

    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("[MQTT] WiFi not connected, MQTT connect skipped.");
        return;
    }

    Serial.println();
    Serial.println("[MQTT] Connecting to broker...");
    Serial.print("[MQTT] Broker: ");
    Serial.print(MQTT_BROKER_HOST);
    Serial.print(":");
    Serial.println(MQTT_BROKER_PORT);

    mqttClient.connect();
}


// =======================
// 初始化 MQTT 客户端
// =======================
void initMqttClient()
{
    if (!mqttCallbacksConfigured)
    {
        mqttClient.onConnect(onMqttConnect);
        mqttClient.onDisconnect(onMqttDisconnect);
        mqttClient.onPublish(onMqttPublish);

        mqttCallbacksConfigured = true;
    }

    mqttClient.setServer(MQTT_BROKER_HOST, MQTT_BROKER_PORT);
    mqttClient.setClientId(MQTT_CLIENT_ID);
    mqttClient.setKeepAlive(MQTT_KEEPALIVE_SEC);
    mqttClient.setCleanSession(true);

    connectMqttBroker();
}


// =======================
// loop 中维护 MQTT 连接
// AsyncMqttClient 不需要 mqttClient.loop()
// 只需要在断开时定时重连
// =======================
void handleMqttClient()
{
    if (WiFi.status() != WL_CONNECTED)
    {
        mqttConnected = false;
        return;
    }

    if (!mqttConnected)
    {
        unsigned long now = millis();

        if (now - lastMqttReconnectAttempt >= MQTT_RECONNECT_INTERVAL_MS)
        {
            lastMqttReconnectAttempt = now;
            connectMqttBroker();
        }
    }
}


// =======================
// 判断 MQTT 是否连接
// =======================
bool isMqttConnected()
{
    return mqttConnected;
}


// =======================
// QoS 1 发布传感器数据
// Topic：env_monitor/{node_id}/{data_type}
// Payload：{"n":"node03","d":"temperature","v":26.31,"t":epoch毫秒,"s":1}
// =======================
bool publishSensorDataQoS1(const SensorData& data)
{
    if (!mqttConnected)
    {
        Serial.println("[MQTT] Not connected, publish skipped.");
        return false;
    }

    uint64_t epochMillis = getEpochMillis();

    String topic = buildMqttTopic(data);
    String payload = buildCompactJsonPayload(data, epochMillis);

    uint16_t packetId = mqttClient.publish(
        topic.c_str(),
        MQTT_QOS_LEVEL,
        false,
        payload.c_str()
    );

    Serial.println("----------------------------------------");
    Serial.print("[MQTT] Topic: ");
    Serial.println(topic);

    Serial.print("[MQTT] Payload: ");
    Serial.println(payload);

    Serial.print("[MQTT] QoS: ");
    Serial.println(MQTT_QOS_LEVEL);

    Serial.print("[MQTT] Packet ID: ");
    Serial.println(packetId);

    if (packetId > 0)
    {
        Serial.println("[MQTT] Publish result: sent");
        return true;
    }
    else
    {
        Serial.println("[MQTT] Publish result: failed");
        return false;
    }
}


// =======================
// 兼容函数名
// =======================
bool publishSensorDataQos1(const SensorData& data)
{
    return publishSensorDataQoS1(data);
}