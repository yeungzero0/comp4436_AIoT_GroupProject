# AIoT-Based - Simulation Smart Parking System (COMP4436)

[![Arduino](https://img.shields.io/badge/Arduino-328P-blue)](https://www.arduino.cc/)
[![Python](https://img.shields.io/badge/Python-3.9-blue)](https://www.python.org/)
[![Node-RED](https://img.shields.io/badge/Node--RED-Dashboard-red)](https://nodered.org/)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-green)](https://mqtt.org/)
[![ThingSpeak](https://img.shields.io/badge/ThingSpeak-Cloud-orange)](https://thingspeak.com/)

**POLYU COMP4436 Artificial Intelligence of Things (AIoT) - Group Project**  
一個基於 AIoT 的智能停車場系統，結合硬體感測、雲端資料傳輸、SNN 預測模型與 Node-RED 即時儀表板，能夠實時監測停車位使用情況、提供動態定價建議及長期使用模式分析。

---

## ⚠️ 免責聲明 (Disclaimer)

**本專案純粹用於學習與課程用途**。

- 此專案是 **POLYU COMP4436 Group 12** 的課程作業，主要目的是展示 IoT 硬體、MQTT 通訊、雲端資料處理及 SNN 預測在 AIoT 應用中的整合。
- **嚴禁商業使用**：本專案**不得**用於任何商業活動、產品開發或生產環境。
- **僅供參考與教育**：所有程式碼、資料與報告僅供個人學習、測試與參考之用。
- **無任何保證**：作者不對使用本專案所產生的任何輸出、系統異常或後果承擔任何責任。

> **總之：這只是我們在 POLYU 學習 AIoT 的課程專案，不是專業商用解決方案。**

---

## 專案特色

- **硬體層**：3 個 HC-SR04 超音波感測器 + Arduino Uno，實時偵測停車位占用（距離 ≤ 50cm 視為占用）
- **資料傳輸**：Arduino 每秒偵測，每分鐘透過 Serial 傳送資料 → Python 後端
- **雲端整合**：ThingSpeak 儲存 7 天歷史數據 + MQTT 即時推送
- **智能預測**：使用 **SNN (Spiking Neural Network)** + Nengo 進行未來占用率預測
- **視覺化儀表板**：Node-RED 提供即時狀態、每日趨勢、尖峰使用時間、動態定價建議、週期性模式分析
- **動態定價**：根據占用率自動建議提高/降低收費（High/Low Demand Strategy）

---

## Demo Video

![image](https://github.com/yeungzero0/comp4436_AIoT_GroupProject/blob/main/AIoT2025_Timg.png)
https://youtu.be/eZ4Px_n9w24  

