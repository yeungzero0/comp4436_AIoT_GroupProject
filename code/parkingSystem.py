import serial
import csv
from datetime import datetime, date, timedelta
import time
import numpy as np
import paho.mqtt.client as mqtt
import requests
import json
import pytz
import pandas as pd
import nengo
import os
import contextlib

# ---Configure---
recommendationsTest = True  # Demo flag for testing recommendations

# Serial port
ser = serial.Serial('COM4', 115200, timeout=1)  # Adjust COM port

# MQTT setup
mqtt_broker = "test.mosquitto.org"
port = 1883
mqtt_client = mqtt.Client()

# ThingSpeak
THINGSPEAK_URL = "https://api.thingspeak.com/update?api_key=ESGJY036JTFJZBH8"
API_KEY = 'XTKTJK5WRLSP6BF9'
CHANNEL_ID = 2909595
THINGSPEAK_FEEDS_URL = f'https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json'
HK_TZ = pytz.timezone('Asia/Hong_Kong')
UTC_TZ = pytz.UTC

# Pricing parameters
BASE_PRICE = 20.0  # Base price per hour (HKD)
HIGH_DEMAND_THRESHOLD = 60.0  # Occupancy % for high demand
LOW_DEMAND_THRESHOLD = 40.0  # Occupancy % for low demand
PRICE_INCREMENT = 2.0  # Price increase for high demand
PRICE_DISCOUNT = 3.0  # Price discount for low demand

# ---Connect to MQTT---
try:
    mqtt_client.connect(mqtt_broker, port)
    print("Connected to MQTT broker successfully!")
except Exception as e:
    print(f"Failed to connect to MQTT broker: {e}")


# Initialize dashboard with last ThingSpeak data
params = {'api_key': API_KEY, 'results': 1}
response = requests.get(THINGSPEAK_FEEDS_URL, params=params)
if response.status_code == 200 and response.json()['feeds']:
    data = response.json()
    last_entry = data['feeds'][0]
    #utc to hk
    utc_time = datetime.strptime(last_entry['created_at'], '%Y-%m-%dT%H:%M:%SZ')
    utc_time = utc_time.replace(tzinfo=pytz.utc)
    hk_time = utc_time.astimezone(HK_TZ)
    initializedata = {
        "datetime": hk_time.strftime('%Y-%m-%d %H:%M:%S'),
        "sensor1": bool(last_entry.get('field1', '1') == '1'),
        "sensor2": bool(last_entry.get('field2', '1') == '1'),
        "sensor3": bool(last_entry.get('field3', '1') == '1')
    }
else:
    initializedata = {
        "datetime": datetime.now(HK_TZ).strftime('%Y-%m-%d %H:%M:%S'),
        "sensor1": True,
        "sensor2": True,
        "sensor3": True
    }
mqtt_client.publish("gp_p10/sensor/data", json.dumps(initializedata))
print(f"Initialized MQTT: {initializedata}")


# ---Fetch Historical Data---
def fetch_historical_data(days=7):
    end_date = datetime.now(HK_TZ)
    #start_date = end_date - timedelta(days=days)
    start_date = (end_date - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    start_date_utc = start_date.astimezone(UTC_TZ)
    end_date_utc = end_date.astimezone(UTC_TZ)
    params = {
        'api_key': API_KEY,
        'start': start_date_utc.strftime('%Y-%m-%d %H:%M:%S'),
        'end': end_date_utc.strftime('%Y-%m-%d %H:%M:%S')
    }
    #print(start_date_utc.strftime('%Y-%m-%d %H:%M:%S'),"\n\n\n\n")
    try:
        response = requests.get(THINGSPEAK_FEEDS_URL, params=params)
        if response.status_code == 200:
            data = response.json()['feeds']
            if not data:
                print("No historical data found.")
                return pd.DataFrame()
            df = pd.DataFrame(data)
            if 'created_at' not in df.columns:
                print("No valid timestamp data in feeds.")
                return pd.DataFrame()
            df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert(HK_TZ)
            for field in ['field1', 'field2', 'field3']:
                df[field] = df[field].fillna(1).astype(float).astype(int)
            return df
        else:
            print(f"Failed to fetch historical data: {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

def aggregated_daily_utilization(days=7):
    """
    Calculate daily parking utilization trends over the specified number of days.
    Returns a DataFrame with daily metrics and publishes to MQTT.
    """
    df = fetch_historical_data(days)
    if df.empty:
        print("No data for daily utilization analysis.")
        return pd.DataFrame()

    try:
        # Convert created_at to date for grouping
        df['Reocrd_DATE'] = df['created_at'].dt.date
        # Calculate occupancy (0=occupied, 1=available, so invert for occupancy)
        df['space1_occupied'] = 1 - df['field1']
        df['space2_occupied'] = 1 - df['field2']
        df['space3_occupied'] = 1 - df['field3']
        df['total_occupied'] = df['space1_occupied'] + df['space2_occupied'] + df['space3_occupied']

        # Group by date
        daily_stats = df.groupby('Reocrd_DATE').agg({
            'space1_occupied': 'mean',
            'space2_occupied': 'mean',
            'space3_occupied': 'mean',
            'total_occupied': 'sum'  # Total occupied instances per day
        }).reset_index()

        # Convert mean to percentage (mean is fraction of time occupied)
        daily_stats['space1_occupancy_rate'] = (daily_stats['space1_occupied'] * 100).round(2)
        daily_stats['space2_occupancy_rate'] = (daily_stats['space2_occupied'] * 100).round(2)
        daily_stats['space3_occupancy_rate'] = (daily_stats['space3_occupied'] * 100).round(2)
        daily_stats['avg_occupancy_rate'] = (
            (daily_stats['space1_occupied'] + daily_stats['space2_occupied'] + daily_stats['space3_occupied']) / 3 * 100
        ).round(2)

        # Rename columns for clarity
        daily_stats = daily_stats[['Reocrd_DATE', 'space1_occupancy_rate', 'space2_occupancy_rate', 
                                  'space3_occupancy_rate', 'avg_occupancy_rate', 'total_occupied']]
        print("\n=== Daily Parking Utilization Trends (last 7 day & Today) ===")
        print(daily_stats.to_string(index=False))
        mqtt_msg = daily_stats.to_string(index=False)
        mqtt_client.publish("gp_p10/parking/daily", mqtt_msg)
        print(f"Published to MQTT 'Topic:gp_p10/parking/daily'\n")

        return daily_stats
    except Exception as e:
        print(f"Error in daily utilization analysis: {e}")
        return pd.DataFrame()

# ---Dynamic Pricing Recommendations---
def dynamic_pricing_recommendation(hourly_stats):
    pricing_data = []
    for _, row in hourly_stats.iterrows():
        occupancy_rate = row['total_occupancy_rate']
        hour_start = int(row['hour'])
        hour_end = (hour_start + 1) % 24
        if occupancy_rate > HIGH_DEMAND_THRESHOLD:
            price = BASE_PRICE + PRICE_INCREMENT
            strategy = "Increase (High Demand)"
        elif occupancy_rate < LOW_DEMAND_THRESHOLD:
            price = BASE_PRICE - PRICE_DISCOUNT
            strategy = "Discount (Low Demand)"
        else:
            price = BASE_PRICE
            strategy = "Maintain (Moderate Demand)"
        pricing_data.append({
            "hour": f"{hour_start:02d}00-{hour_end:02d}00",
            "occupancy_rate": occupancy_rate,
            "recommended_price": max(price, 1.0),
            "strategy": strategy
        })
    
    print("\n=== Dynamic Pricing Recommendations ===")
    for entry in pricing_data:
        print(f"Hour {entry['hour']}: Occupancy {entry['occupancy_rate']}%, "
              f"Price {entry['recommended_price']} HKD ({entry['strategy']})")
    
    mqtt_client.publish("gp_p10/parking/pricing", json.dumps(pricing_data))
    print("Published pricing recommendations to MQTT 'Topic:gp_p10/parking/pricing'")
    return pricing_data

def calculate_price(occupancy_rate):
    if occupancy_rate > HIGH_DEMAND_THRESHOLD:
        return BASE_PRICE + PRICE_INCREMENT
    elif occupancy_rate < LOW_DEMAND_THRESHOLD:
        return BASE_PRICE - PRICE_DISCOUNT
    return BASE_PRICE

def analyze_peak_usage_and_patterns(days=7):
    df = fetch_historical_data(days)
    if df.empty:
        print("No data for peak usage analysis.")
        return
    
    try:
        df['space1_occupied'] = 1 - df['field1']
        df['space2_occupied'] = 1 - df['field2']
        df['space3_occupied'] = 1 - df['field3']
        df['hour'] = df['created_at'].dt.hour
        df['day_of_week'] = df['created_at'].dt.dayofweek
        
        # Hourly occupancy
        hourly_stats = df.groupby('hour').agg({
            'space1_occupied': 'mean',
            'space2_occupied': 'mean',
            'space3_occupied': 'mean'
        }).reset_index()
        hourly_stats['total_occupancy_rate'] = (
            (hourly_stats[['space1_occupied', 'space2_occupied', 'space3_occupied']].mean(axis=1)) * 100
        ).round(2)
        
        # Peak hours
        top_3_hours = hourly_stats.sort_values('total_occupancy_rate', ascending=False).head(3)

        # Sort the top 3 hours by hour for user-friendly display
        top_3_hours = top_3_hours.sort_values('hour')

        print("\n=== Peak Usage Times ===")
        for _, row in top_3_hours.iterrows():
            hour_start = int(row['hour'])
            hour_end = (hour_start + 1) % 24
            print(f"Hour {hour_start:02d}00-{hour_end:02d}00: (Total occupancy rate: {row['total_occupancy_rate']}%)")
        
        mqtt_peak_data = {
            "peak_hours": [
                {"hour": f"{int(row['hour']):02d}00-{(int(row['hour'])+1)%24:02d}00",
                 "total_occupancy_rate": row['total_occupancy_rate']}
                for _, row in top_3_hours.iterrows()
            ]
        }
        mqtt_client.publish("gp_p10/parking/peak_usage", json.dumps(mqtt_peak_data))
        print("Published peak usage to MQTT 'Topic:gp_p10/parking/peak_usage'")
        
        # Dynamic pricing
        dynamic_pricing_recommendation(hourly_stats)
        
        # Recurring patterns
        patterns = df.groupby(['day_of_week', 'hour']).agg({
            'space1_occupied': 'mean',
            'space2_occupied': 'mean',
            'space3_occupied': 'mean'
        }).reset_index()
        patterns['avg_occupancy_rate'] = (
            (patterns[['space1_occupied', 'space2_occupied', 'space3_occupied']].mean(axis=1)) * 100
        ).round(2)
        
        weekday_occupancy = patterns[patterns['day_of_week'] < 5]['avg_occupancy_rate'].mean()
        weekend_occupancy = patterns[patterns['day_of_week'] >= 5]['avg_occupancy_rate'].mean()
        print("\n=== Recurring Occupancy Patterns ===")
        print(f"Average Weekday Occupancy: {0.0 if pd.isna(weekday_occupancy) else weekday_occupancy:.2f}%")
        print(f"Average Weekend Occupancy: {0.0 if pd.isna(weekend_occupancy) else weekend_occupancy:.2f}%")
        
        mqtt_patterns_data = {
            "weekday_occupancy": float(weekday_occupancy) if not pd.isna(weekday_occupancy) else 0.0,
            "weekend_occupancy": float(weekend_occupancy) if not pd.isna(weekend_occupancy) else 0.0
        }
        mqtt_client.publish("gp_p10/parking/patterns", json.dumps(mqtt_patterns_data))
        print("Published patterns to MQTT 'Topic:gp_p10/parking/patterns'")
        
        
    except Exception as e:
        print(f"Error in peak usage/pattern analysis: {e}")

def build_snn_model(data):
    if nengo is None or data.empty:
        print("Cannot build SNN: Nengo unavailable or no data.")
        return None, None, None, None, None
    try:
        # Extract features and labels
        data['hour'] = data['created_at'].dt.hour
        data['day_of_week'] = data['created_at'].dt.dayofweek
        X = data[['hour', 'day_of_week']].values  # Shape: (n_samples, 2)
        y = data[['field1', 'field2', 'field3']].values  # Shape: (n_samples, 3)
        
        # Normalize inputs
        X_mean = X.mean(axis=0)
        X_std = X.std(axis=0) + 1e-8
        X_normalized = (X - X_mean) / X_std
        
        # Create Nengo network
        model = nengo.Network()
        with model:
            # Input node (2D: hour, day_of_week)
            input_node = nengo.Node([0, 0])
            # Target output node for training
            target_node = nengo.Node([0, 0, 0])
            
            # Ensembles
            neurons = 100
            ensemble = nengo.Ensemble(n_neurons=neurons, dimensions=2, neuron_type=nengo.LIF())
            output = nengo.Ensemble(n_neurons=neurons, dimensions=3, neuron_type=nengo.LIF())
            
            # Connections
            nengo.Connection(input_node, ensemble)
            conn = nengo.Connection(ensemble, output, transform=np.zeros((3, 2)), learning_rule_type=nengo.PES(learning_rate=1e-4))
            # Error connection for learning
            nengo.Connection(output, conn.learning_rule, transform=-1)
            nengo.Connection(target_node, conn.learning_rule)
            
            # Probe output
            probe_output = nengo.Probe(output, synapse=0.01)
        
        # Create simulator
        sim = nengo.Simulator(model)
        print(f"\nTraining SNN Model with {len(X_normalized)} data... \nPlease Wait... ")

        @contextlib.contextmanager
        def suppress_output():
            with open(os.devnull, 'w') as fnull:
                with contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
                    yield

        
        start_time = time.time()
        # Training loop (simple simulation-based training)
        for i in range(len(X_normalized)):
            sim.reset()
            input_node.output = X_normalized[i]
            target_node.output = y[i]
            
            with suppress_output():
                sim.run(0.1)  # Run for a short time per sample
                # Optionally log the time taken
            
            if i % 40 == 0:  # Log every 20 iterations, for example
                elapsed_time = time.time() - start_time
                print(f"Simulation for data {i} finished in {elapsed_time:.2f} seconds.")
        
        return model, sim, probe_output, X_mean, X_std
    except Exception as e:
        print(f"Error building SNN model: {e}")
        return None, None, None, None, None

def predict_snn(model, sim, probe_output, hour, day_of_week, X_mean, X_std):
    if model is None or sim is None:
        return [1, 1, 1]
    try:
        # Normalize input
        normalized_input = [(hour - X_mean[0]) / X_std[0], (day_of_week - X_mean[1]) / X_std[1]]
        
        # Reset simulator
        sim.reset()
        
        with model:
            input_node = model.nodes[0]
            input_node.output = normalized_input  # Set input for one time step
            
            # Run simulation for a short time to get steady-state output
            sim.run(0.5)
            
            # Get the last output
            prediction = sim.data[probe_output][-1]
            
            # Convert to binary (available=1, occupied=0)
            return (prediction > 0).astype(int)  
    except Exception as e:
        print(f"Error predicting with SNN: {e}")
        return [1, 1, 1]

# ---Optimize Allocation---
def recommend_allocation(predictions):
    #print(predictions,"\n")
    available_spaces = [i+1 for i, p in enumerate(predictions) if p == 1]
    pricing = "Should be Higher" if sum(predictions) < 2 else "Should be Lower"
    reservation = "Enough_Space" if available_spaces else "More_Space"
    return {
        "available_spaces": available_spaces,
        "pricing": pricing,
        "reservation": reservation
    }

# ---CSV Setup---
csv_file = open('parking_data.csv', 'a', newline='')
csv_writer = csv.writer(csv_file)
if csv_file.tell() == 0:
    csv_writer.writerow(['Timestamp', 'Sensor1', 'Sensor2', 'Sensor3'])

print("Listening for data from Arduino...")

# ---Main Loop---
try:
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').strip()
            if line:
                print(f"Received: {line}")
                data = line.split(',')
                if data[0] == "date":
                    timestamp = datetime.now(HK_TZ).strftime('%Y-%m-%d %H:%M:%S')
                    data[0] = timestamp
                    csv_writer.writerow(data)
                    csv_file.flush()
                    s1 = int(data[1] == "True")
                    s2 = int(data[2] == "True")
                    s3 = int(data[3] == "True")
                    psdata = {
                        "datetime": timestamp,
                        "sensor1": data[1],
                        "sensor2": data[2],
                        "sensor3": data[3]
                    }
                    mqtt_client.publish("gp_p10/sensor/data", json.dumps(psdata))
                    print(f"Published to MQTT 'Topic:gp_p10/sensor/data': {psdata}")
                    response = requests.get(f"{THINGSPEAK_URL}&field1={s1}&field2={s2}&field3={s3}")
                    if response.status_code == 200:
                        print(f"\nSent to ThingSpeak: \nparking space1 is available: {data[1]} "
                              f"\nparking space2 is available: {data[2]} \nparking space3 is available: {data[3]}")
                    else:
                        print(f"ThingSpeak error: {response.status_code}")
                
                now = datetime.now(HK_TZ)
                current_time = now.strftime("%H:%M:%S")
                if ("23:55:00" <= current_time <= "23:59:59") or recommendationsTest:
                    recommendationsTest = False
                    print(f"\n=== Performing Daily Analysis at {current_time} ===")
                    aggregated_daily_utilization()
                    analyze_peak_usage_and_patterns()

                    historical_data = fetch_historical_data()
                    if historical_data.empty:
                        print("Skipping prediction - no historical data available")
                        continue

                    model, sim, probe_output, X_mean, X_std = build_snn_model(historical_data)
                    if None in (model, sim, probe_output):
                        print("Skipping prediction - SNN model failed to initialize")
                        continue

                    try:
                        prediction = predict_snn(model, sim, probe_output, now.hour, now.weekday(), X_mean, X_std)
                        recommendations = recommend_allocation(prediction)
                        rec_data = {
                            "prediction_datetime": now.strftime('%Y-%m-%d %H:%M:%S'),
                            #"predicted_availability": prediction.tolist(),
                            "recommendations": recommendations
                        }
                        mqtt_client.publish("gp_p10/sensor/predictions", json.dumps(rec_data))
                        print(f"Published predictions 'Topic:gp_p10/sensor/predictions': {rec_data}\n")

                    except Exception as e:
                        print(f"Analysis failed: {str(e)}")
                
except KeyboardInterrupt:
    print("Stopped by user.")
finally:
    ser.close()
    csv_file.close()
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    print("Serial connection closed, CSV file saved, and MQTT disconnected.")